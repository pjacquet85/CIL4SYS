import numpy as np

from gym.spaces.tuple_space import Tuple
from gym.spaces.box import Box

from flow.envs import Env

class IssyEnvAbstract(Env):
    """Abstract class to inherit from. It provides helpers
    used accross models such as a traffic light state inversion method"""

    def _invert_tl_state(self, id, api="sumo"):
        """Invert state for given traffic light.
        It currently only implements conversion for the sumo light state.
        This function returns the new state string (of the same length as the input state),
        this allows for handling intersections with different numbers of lanes and lights
        elegantly.

        This function takes any sumo light state but only convets to a "green" or "red" state.
        Orange and other states are converted accordingly, see implementation for more detail.

        Parameters
        ----------
        id: str
            ID of traffic light to invert
            Use `flow.kernel.traffic_light.get_ids` to get a list of traffic light ids.
        api: str
            Simulator API which defines the light state format to return. Currently only
            implements the sumo traffic state format.
            (see: https://sumo.dlr.de/wiki/Simulation/Traffic_Lights#Signal_state_definitions)

        Returns
        ----------
        new_state: str
            New light state consisting of only red and green lights that oppose the previous state
            as much as possible.

        """
        if api == "sumo":
            old_state = self.k.traffic_light.get_state(id)
            state = old_state.replace("g", "G")
            state = state.replace("y", "r")
            state = state.replace("G", "tmp")
            state = state.replace("r", "G")
            state = state.replace("tmp", "r")
            return state
        else:
            return NotImplementedError

class IssyEnv1(IssyEnvAbstract):
    """Environment used to train traffic lights to regulate traffic flow
    for the Issy les Moulineaux district of study.

    Required from env_params:

    * beta: (int) number of vehicles the agent can observe

    States
        An observation is the distance of each vehicle to its intersection, a
        number uniquely identifying which edge the vehicle is on, and the speed
        of the vehicle.

    Actions
        The action space consist of a list of float variables ranging from 0-1
        specifying whether a traffic light is supposed to switch or not. The
        actions are sent to the traffic light in the grid from left to right
        and then top to bottom.

    Rewards
        The reward is the negative per vehicle delay minus a penalty for
        switching traffic lights

    Termination
        A rollout is terminated once the time horizon is reached.

    Additional
        Vehicles are rerouted to the start of their original routes once they
        reach the end of the network in order to ensure a constant number of
        vehicles.
    """
    def __init__(self, env_params, sim_params, scenario, simulator='traci'):
        super().__init__(env_params, sim_params, scenario, simulator)
        model_spec = env_params.get_additional_param("model_spec")
        self.model_spec = model_spec

    @property
    def action_space(self):
        """See parent class"""
        return Box(low=0, high=1, shape=(self.k.traffic_light.num_traffic_lights,),
                dtype=np.float32)

    @property
    def observation_space(self):
        """See parent class"""
        return Box(
            low=0,
            high=float("inf"),
            shape=(2*self.scenario.vehicles.num_vehicles,),
        )

    def get_state(self, **kwargs):
        """See parent class"""
        # We select beta=20 observable vehicles
        ids = self.k.vehicle.get_ids()[:20]

        pos = [self.k.vehicle.get_x_by_id(veh_id) for veh_id in ids]
        vel = [self.k.vehicle.get_speed(veh_id) for veh_id in ids]
        tl = [self.k.traffic_light.get_state(t) for t in self.k.traffic_light.get_ids()]

        return np.concatenate((pos, vel))


    def _apply_rl_actions(self, rl_actions):
        """See parent class"""
        tl_ids = self.k.traffic_light.get_ids()
        actions = np.round(rl_actions)

        for id, a in zip(tl_ids, actions):
            if a:
                state = self._invert_tl_state(id)
                self.k.traffic_light.set_state(id, state)

    def compute_reward(self, rl_actions, **kwargs):
        """See parent class"""
        ids = self.k.vehicle.get_ids()
        speeds = self.k.vehicle.get_speed(ids)

        return np.mean(speeds)
