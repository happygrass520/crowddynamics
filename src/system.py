from collections import Iterable
from timeit import default_timer as timer

from src.core.integrator import euler_method, euler_method2, euler_method0
from src.display import format_time
from src.struct.result import Result
from src.visualization.animation import animation


class System:
    def __init__(self, constant, agent, wall=None, goals=None):
        self.constant = constant
        self.agent = agent
        self.wall = wall
        self.goals = goals

        if not isinstance(self.wall, Iterable):
            self.wall = (self.wall,)
        self.wall = tuple(filter(None, self.wall))

        if not isinstance(self.goals, Iterable):
            self.goals = (self.goals,)
        self.goals = tuple(filter(None, self.goals))

        self.result = Result(agent.size)

        # System
        if len(self.wall) == 0:
            self.integrator = euler_method0(self.result,
                                            self.constant,
                                            self.agent)
        if len(self.wall) == 1:
            self.integrator = euler_method(self.result,
                                           self.constant,
                                           self.agent,
                                           *self.wall)
        elif len(self.wall) == 2:
            self.integrator = euler_method2(self.result,
                                            self.constant,
                                            self.agent,
                                            *self.wall)
        else:
            raise ValueError()

        self.prev_time = 0

    def animation(self, x_dims, y_dims, save=False, frames=None, filepath=None):
        animation(self, x_dims, y_dims, save, frames, filepath)

    def exhaust(self):
        for _ in self:
            pass

    def print_stats(self):
        out = "i: {:06d} | {:04d} | {} | {}".format(
            self.result.iterations,
            self.result.agents_in_goal,
            format_time(self.result.avg_wall_time()),
            format_time(self.result.wall_time_tot),
        )
        print(out)

    def goal_reached(self, goal):
        num = goal.is_reached_by(self.agent)
        for _ in range(num):
            if self.result.increment_agent_in_goal():
                self.print_stats()
                raise GeneratorExit()

    def __iter__(self):
        return self

    def __next__(self):
        """
        Generator exits when all agents have reached their goals.
        """
        try:
            # TODO: Goal direction updating
            # self.agent.set_goal_direction(goal_point)

            # Execution timing
            start = timer()
            ret = next(self.integrator)
            t_diff = timer() - start
            self.result.increment_wall_time(t_diff)

            # Printing
            if self.result.wall_time_tot - self.prev_time > 1.0:
                self.prev_time = self.result.wall_time_tot
                self.print_stats()

            # Check goal
            for goal in self.goals:
                self.goal_reached(goal)

            return ret
        except GeneratorExit:
            raise StopIteration()