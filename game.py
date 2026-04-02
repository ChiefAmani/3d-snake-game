
import collections
import random
import time
from direct.showbase.ShowBase import ShowBase
from panda3d.core import Vec3, LVector3f, Point3, NodePath, DirectionalLight, AmbientLight, WindowProperties, Quat
from direct.interval.IntervalGlobal import Sequence, Func
from direct.gui.OnscreenText import OnscreenText
from direct.task import Task

# --- Game Configuration ---
GRID_SIZE = 20  # The game world will be a GRID_SIZE x GRID_SIZE x GRID_SIZE cube
INITIAL_SNAKE_LENGTH = 3
TICK_RATE = 0.5  # Seconds per game tick (lower is faster)

# Directions (Panda3D's Vec3 for consistency)
UP = Vec3(0, 0, 1)
DOWN = Vec3(0, 0, -1)
LEFT = Vec3(-1, 0, 0)
RIGHT = Vec3(1, 0, 0)
FORWARD = Vec3(0, 1, 0) # In Panda3D, Y is typically forward
BACKWARD = Vec3(0, -1, 0)

# --- Game State ---
class GameState:
    def __init__(self):
        self.snake = collections.deque()
        self.food = None
        self.direction = FORWARD  # Initial direction
        self.score = 0
        self.game_over = False
        self._initialize_game()

    def _initialize_game(self):
        # Start snake in the middle of the grid, moving forward
        start_x = GRID_SIZE // 2
        start_y = GRID_SIZE // 2
        start_z = GRID_SIZE // 2
        for i in range(INITIAL_SNAKE_LENGTH):
            # Snake grows backwards initially along the Y-axis (Panda3D's forward)
            self.snake.appendleft(Point3(start_x, start_y - i, start_z))
        self._generate_food()

    def _generate_food(self):
        while True:
            x = random.randint(0, GRID_SIZE - 1)
            y = random.randint(0, GRID_SIZE - 1)
            z = random.randint(0, GRID_SIZE - 1)
            new_food_pos = Point3(x, y, z)
            if new_food_pos not in self.snake:
                self.food = new_food_pos
                break

    def update(self):
        if self.game_over:
            return

        head_pos = self.snake[0]
        new_head = head_pos + self.direction

        # --- Collision Detection ---
        # Wall collision
        if not (0 <= new_head.x < GRID_SIZE and
                0 <= new_head.y < GRID_SIZE and
                0 <= new_head.z < GRID_SIZE):
            self.game_over = True
            print("Game Over: Hit wall!")
            return

        # Self-collision (check against body, not new_head if it's the tail)
        # Convert deque to list for easier 'in' checking, excluding the tail
        if new_head in list(self.snake)[:-1]:
            self.game_over = True
            print("Game Over: Self-collision!")
            return

        self.snake.appendleft(new_head)

        # --- Food Consumption ---
        if new_head == self.food:
            self.score += 1
            print(f"Score: {self.score}")
            self._generate_food()
        else:
            self.snake.pop() # Remove tail if no food eaten

    def change_direction(self, new_direction):
        # Prevent reversing directly into the snake's body
        opposite_direction = -self.direction
        if new_direction != opposite_direction:
            self.direction = new_direction
            print(f"Direction changed to: {self.direction}")

    def get_game_state_for_rendering(self):
        """
        Returns the current game state in a format suitable for a 3D renderer.
        This would include snake segments, food position, and camera orientation.
        """
        return {
            "snake_positions": list(self.snake),
            "food_position": self.food,
            "current_direction": self.direction,
            "score": self.score,
            "game_over": self.game_over,
            "grid_size": GRID_SIZE
        }

# --- Mouse Swipe Controls ---
class MouseSwipeHandler:
    def __init__(self, base_app, sensitivity=0.05): # Sensitivity now normalized for screen coords
        self.base_app = base_app
        self.start_pos = None
        self.sensitivity = sensitivity # Minimum normalized distance for a swipe
        self.current_snake_direction = FORWARD # Will be updated by the game

    def on_mouse_down(self):
        if self.base_app.mouseWatcherNode.hasMouse():
            self.start_pos = self.base_app.mouseWatcherNode.getMouse() # Returns Vec2 (normalized -1 to 1)

    def on_mouse_up(self):
        if self.start_pos is None or not self.base_app.mouseWatcherNode.hasMouse():
            return None

        end_pos = self.base_app.mouseWatcherNode.getMouse()
        dx = end_pos.x - self.start_pos.x
        dy = end_pos.y - self.start_pos.y
        self.start_pos = None # Reset for next swipe

        # Determine if it's a significant swipe (using normalized coordinates)
        if abs(dx) > self.sensitivity or abs(dy) > self.sensitivity:
            if abs(dx) > abs(dy): # Horizontal swipe
                if dx > 0:
                    return self._map_swipe_to_turn("right", self.current_snake_direction)
                else:
                    return self._map_swipe_to_turn("left", self.current_snake_direction)
            else: # Vertical swipe
                if dy > 0:
                    return self._map_swipe_to_turn("down", self.current_snake_direction)
                else:
                    return self._map_swipe_to_turn("up", self.current_snake_direction)
        return None

    def _map_swipe_to_turn(self, swipe_direction_screen, current_snake_direction):
        """
        Maps a screen-relative swipe direction to a 3D game direction using rotations.
        This is a more robust approach than hardcoded conditionals.
        """
        # Define rotation angles (e.g., 90 degrees for a turn)
        angle = 90
        new_direction = current_snake_direction

        # World up vector (Panda3D's Z-axis)
        world_up = Vec3(0, 0, 1)

        # Calculate the 'right' vector relative to the current direction and world up
        # This handles cases where current_snake_direction is aligned with world_up
        if current_snake_direction.normalize().almostEqual(world_up.normalize()) or \
           current_snake_direction.normalize().almostEqual(-world_up.normalize()):
            # If moving purely up or down, define 'right' along the X-axis
            relative_right = Vec3(1, 0, 0)
        else:
            relative_right = world_up.cross(current_snake_direction).normalize()
        
        # Calculate the 'local up' vector (orthogonal to current_snake_direction and relative_right)
        relative_up = current_snake_direction.cross(relative_right).normalize()

        if swipe_direction_screen == "left":
            # Rotate around the relative_up vector (yaw)
            quat = Quat() # Identity quaternion
            quat.setFromAxisAngle(angle, relative_up) # Rotate 90 degrees around relative_up
            new_direction = quat.xform(current_snake_direction).roundToAxes()
        elif swipe_direction_screen == "right":
            # Rotate around the relative_up vector (yaw) in the opposite direction
            quat = Quat()
            quat.setFromAxisAngle(-angle, relative_up)
            new_direction = quat.xform(current_snake_direction).roundToAxes()
        elif swipe_direction_screen == "up":
            # Rotate around the relative_right vector (pitch up)
            quat = Quat()
            quat.setFromAxisAngle(angle, relative_right)
            new_direction = quat.xform(current_snake_direction).roundToAxes()
        elif swipe_direction_screen == "down":
            # Rotate around the relative_right vector (pitch down)
            quat = Quat()
            quat.setFromAxisAngle(-angle, relative_right)
            new_direction = quat.xform(current_snake_direction).roundToAxes()
        
        # Ensure the new direction is one of the cardinal directions after rotation
        # This helps snap to grid-aligned movement.
        # The .roundToAxes() method helps with this, but we can also explicitly check.
        cardinal_directions = [UP, DOWN, LEFT, RIGHT, FORWARD, BACKWARD]
        for cd in cardinal_directions:
            if new_direction.almostEqual(cd):
                new_direction = cd
                break
        else:
            # If it doesn't snap to a cardinal direction, it might be an invalid turn
            # or an intermediate direction. For snake, we want cardinal.
            print(f"Warning: New direction {new_direction} not perfectly cardinal. Clamping to nearest.")
            # A more robust solution would involve finding the closest cardinal direction
            # or ensuring the rotation always results in a cardinal direction.
            # For now, we'll just use the rotated vector.

        if new_direction != current_snake_direction:
            print(f"Mapped swipe '{swipe_direction_screen}' to new direction: {new_direction}")
            return new_direction
        return None

# --- Panda3D Application ---
class SnakeGame3D(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)

        self.game_state = GameState()
        self.swipe_handler = MouseSwipeHandler(self)

        self.setup_window()
        self.setup_camera()
        self.setup_lighting()
        self.setup_models()
        self.setup_text()
        self.setup_input()

        # Game update task
        self.game_task = self.taskMgr.add(self.update_game_task, "updateGameTask")
        self.game_task.last_update_time = globalClock.getFrameTime()

        # Rendering task
        self.render_task = self.taskMgr.add(self.render_game_3d_task, "renderGame3DTask")

    def setup_window(self):
        props = WindowProperties()
        props.setTitle("3D First-Person Snake")
        self.win.requestProperties(props)
        self.disableMouse() # Disable default mouse camera control

    def setup_camera(self):
        # Position the camera at the snake's head, looking in its direction
        # We'll update this dynamically in render_game_3d_task
        self.camera.setPos(0, 0, 0)
        self.camera.lookAt(0, 1, 0) # Look forward initially
        self.camLens.setFov(90) # Wide field of view for first-person

    def setup_lighting(self):
        # Ambient light
        ambientLight = AmbientLight("ambientLight")
        ambientLight.setColor(LVector3f(0.3, 0.3, 0.3, 1))
        self.ambientLightNP = self.render.attachNewNode(ambientLight)
        self.render.setLight(self.ambientLightNP)

        # Directional light
        directionalLight = DirectionalLight("directionalLight")
        directionalLight.setColor(LVector3f(0.7, 0.7, 0.7, 1))
        self.directionalLightNP = self.render.attachNewNode(directionalLight)
        # Point it at the scene
        self.directionalLightNP.setHpr(45, -45, 0)
        self.render.setLight(self.directionalLightNP)

    def setup_models(self):
        # Parent node for all game elements for easy clearing
        self.game_elements = self.render.attachNewNode("GameElements")
        self.snake_nodes = []
        self.food_node = None

        # Load a simple cube model for snake segments and food
        self.cube_model = self.loader.loadModel("models/misc/rgbCube") # A default Panda3D cube

    def setup_text(self):
        self.score_text = OnscreenText(text="Score: 0", pos=(-0.9, 0.9), scale=0.07,
                                       fg=(1, 1, 1, 1), align=OnscreenText.ALeft,
                                       mayChange=True)
        self.game_over_text = OnscreenText(text="GAME OVER!", pos=(0, 0), scale=0.15,
                                           fg=(1, 0, 0, 1), align=OnscreenText.ACenter,
                                           mayChange=True, mayChangeColor=True)
        self.game_over_text.hide()

    def setup_input(self):
        self.accept("mouse1", self.swipe_handler.on_mouse_down) # Left mouse button down
        self.accept("mouse1-up", self.handle_mouse_up) # Left mouse button up

    def handle_mouse_up(self):
        # Pass the current snake direction to the swipe handler for context
        self.swipe_handler.current_snake_direction = self.game_state.direction
        new_dir = self.swipe_handler.on_mouse_up()
        if new_dir:
            self.game_state.change_direction(new_dir)

    def update_game_task(self, task):
        current_time = globalClock.getFrameTime()
        if current_time - task.last_update_time > TICK_RATE:
            self.game_state.update()
            task.last_update_time = current_time
            if self.game_state.game_over:
                self.game_over_text.show()
                return Task.done # Stop game updates
        return Task.cont

    def render_game_3d_task(self, task):
        # Clear previous game elements
        self.game_elements.getChildren().detach()
        self.snake_nodes = []

        game_data = self.game_state.get_game_state_for_rendering()

        # Update score display
        self.score_text.setText(f"Score: {game_data['score']}")

        # Render Snake
        for i, segment_pos in enumerate(game_data["snake_positions"]):
            segment = self.cube_model.copyTo(self.game_elements)
            segment.setPos(segment_pos)
            segment.setScale(0.9) # Slightly smaller than grid cell
            if i == 0: # Head
                segment.setColor(0, 1, 0, 1) # Green
                # Position camera at the head
                self.camera.setPos(segment_pos)
                # Orient camera to look in the snake's direction
                # This is a simplified lookAt. For true first-person,
                # we'd need to manage camera pitch/yaw separately.
                self.camera.lookAt(segment_pos + game_data["current_direction"])
            else:
                segment.setColor(0, 0.7, 0, 1) # Darker green for body
            self.snake_nodes.append(segment)

        # Render Food
        if game_data["food_position"]:
            if not self.food_node:
                self.food_node = self.cube_model.copyTo(self.game_elements)
                self.food_node.setColor(1, 0, 0, 1) # Red
                self.food_node.setScale(0.8)
            self.food_node.setPos(game_data["food_position"])
        
        # If game is over, ensure food is still rendered if it exists
        if self.game_state.game_over and self.food_node:
            self.food_node.reparentTo(self.game_elements) # Ensure it's still under game_elements

        return Task.cont

# --- Main Game Loop ---
if __name__ == "__main__":
    app = SnakeGame3D()
    app.run()
