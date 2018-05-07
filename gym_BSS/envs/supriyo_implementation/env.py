import gym
import numpy as np
import os.path
from gym import error, spaces, warnings
from gym.utils import seeding


class BSSEnv(gym.Env):

    def __init__(self, nzones=95, ntimesteps=12, data_dir=None, use_test_data=False):
        super().__init__()
        self.nzones = nzones
        self.ntimesteps = ntimesteps
        self.scenarios = list(range(21, 61)) if use_test_data else list(range(1, 21))
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), "default_data")
        self.data_dir = data_dir
        self.__read_data()
        self.capacities = np.array(self.__cp)
        self.starting_allocation = np.array(self.__ds)
        self.metadata = {
            'render.modes': [],
            'nzones': self.nzones,
            'ntimesteps': self.ntimesteps,
            'nbikes': self.nbikes,
            'capacities': self.capacities,
            'data_dir': self.data_dir,
            'scenarios': self.scenarios
        }
        self.observation_space = spaces.Box(low=0, high=np.inf, shape=[
            self.nzones * 2 + 1], dtype=np.float32)
        self.action_space = spaces.Box(low=0, high=np.inf, shape=[
            self.nzones], dtype=np.float32)
        self._scenario = 20
        self.seed(None)

    def __read_data(self):
        self.__read_capacity_and_starting_allocation(
            os.path.join(self.data_dir, "demand_bound_artificial_60.txt"))
        self.__read_zone_distances(os.path.join(
            self.data_dir, "RawData", "distance_zone.txt"))
        self.__read_demand_data(self.scenarios, os.path.join(
            self.data_dir, "DemandScenarios", "actual-data-art", "DemandScenarios1", "demand_scenario_{scenario}.txt"))

    def __read_capacity_and_starting_allocation(self, filename):
        self.__cp = [0 for k in range(self.nzones)]
        self.__ds = [[0.0 for k in range(self.nzones)] for j in range(
            self.ntimesteps + 1)]  # Distribution is zones
        f = open(filename)
        line = f.readline()

        line = f.readline()
        line = line.strip(" \n")
        line = line.split(" ")
        for s in range(self.nzones):
            self.__cp[s] = int(line[s])

        line = f.readline()
        line = line.strip(" \n")
        line = line.split(" ")
        self.nbikes = 0
        for s in range(0, self.nzones):
            self.__ds[0][s] = int(line[s])
            self.nbikes = self.nbikes + self.__ds[0][s]

        f.close()

    def __read_demand_data(self, scenarios, filename_unformatted):
        self.demand_data = {}
        for scenario in scenarios:
            flow = [[[0.0 for k in range(self.nzones)] for j in range(
                self.nzones)] for i in range(self.ntimesteps)]  # Known Flow
            f2 = open(filename_unformatted.format(scenario=scenario))
            for i in range(self.ntimesteps):
                for j in range(self.nzones):
                    line = f2.readline()
                    line = line.strip(" \r\n")
                    line = line.split(" ")
                    for k in range(self.nzones):
                        flow[i][j][k] = float(line[k])
            f2.close()
            self.demand_data[scenario] = flow

    def __read_zone_distances(self, filename):
        self.__dis = [[0.0 for k in range(self.nzones)]
                      for i in range(self.nzones)]
        f2 = open(filename)
        line = f2.readline()
        ma = 0
        T = 0
        for T in range(self.nzones):
            line = line.strip(' \r\n ')
            line = line.split(" ")
            for i in range(self.nzones):
                self.__dis[T][i] = float(line[i])  # /10000.0
                if(self.__dis[T][i] > ma):
                    ma = self.__dis[T][i]
            line = f2.readline()
        f2.close()

        for i in range(self.nzones):
            self.__dis[i][i] = 0

        self.__mindis = [[-1 for k in range(self.nzones)]
                         for i in range(self.nzones)]
        for i in range(self.nzones):
            sortindex = sorted(
                range(len(self.__dis[i])), key=lambda k: self.__dis[i][k])
            for j in range(self.nzones):
                self.__mindis[i][j] = sortindex[j]

    def seed(self, seed=None):
        if seed is None:
            seed = seeding.create_seed(max_bytes=4)
        self.__nprandom = np.random.RandomState(seed)
        return [seed]

    def _get_observation(self):
        if self.__t == 0:
            demand_2d = np.zeros(shape=[self.nzones, self.nzones])
        else:
            demand_2d = np.array(self.__fl[self.__t - 1])
        assert list(demand_2d.shape) == [self.nzones, self.nzones]
        demand_1d = np.sum(demand_2d, axis=1)
        alloc = np.array(self.__ds[self.__t])
        obs = np.concatenate([demand_1d, alloc, [self.__t]])
        assert list(obs.shape) == list(self.observation_space.shape)
        return obs

    def __reset_allocation(self):
        self.__ds = list(self.starting_allocation)

    def __reset_flow(self, scenario):
        self.__fl = self.demand_data[scenario]
        self.__xfl = [[[0.0 for k in range(self.nzones)] for j in range(
            self.nzones)] for i in range(self.ntimesteps)]  # Actual computed Flow
        self.__tfl1 = [[0.0 for k in range(self.nzones)]
                       for j in range(self.ntimesteps)]

        for t in range(0, self.ntimesteps):
            for s in range(0, self.nzones):
                for s1 in range(0, self.nzones):
                    self.__tfl1[t][s] = self.__tfl1[t][s] + self.__fl[t][s][s1]

    def reset(self):
        # pick up a day at random
        self._scenario = self.scenarios[self.__nprandom.randint(
            len(self.scenarios))]
        # self._scenario = self._scenario + 1
        # print("demand scenario is:", self._scenario)
        self.__reset_allocation()
        self.__reset_flow(self._scenario)

        self.__yp = [[0.0 for k in range(self.nzones)]
                     for j in range(self.ntimesteps)]
        self.__yn = [[0.0 for k in range(self.nzones)]
                     for j in range(self.ntimesteps)]
        self.__t = 0

        return self._get_observation()

    def __set_yp_yn_from_action(self, action):
        if action is None:
            warnings.warn(
                "no action was provided. taking default action of not changing allocation")
        else:
            action = np.array(action)
            if not(hasattr(action, 'shape') and list(action.shape) == list(self.action_space.shape)):
                raise error.InvalidAction(
                    'action shape must be as per env.action_space.shape. Provided action was {0}'.format(action))
            if np.round(np.sum(action)) != self.nbikes:
                raise error.InvalidAction(
                    'Dimensions of action must sum upto env.metadata["nbikes"]. Provided action was {0} with sum {1}'.format(action, sum(action)))
            # if np.any(action > self.capacities):
            #     raise error.InvalidAction(
            #         'Individual dimensions of action must be less than respective dimentions of env.metadata["capacities"]. Provided action was {0}'.format(self.capacities - action))
            alloc_diff = action - np.array(self.__ds[self.__t])
            yp = alloc_diff * (alloc_diff > 0)
            yn = - alloc_diff * (alloc_diff < 0)
            self.__yp[self.__t] = list(yp)
            self.__yn[self.__t] = list(yn)

    def __calculate_lost_demand_new_allocation(self):
        full_lost = 0.0
        iteration = self.__t
        for s in range(self.nzones):
            # and ((yn[iteration][s]-yp[iteration][s])<=cp[s]-ds[iteration][s])):
            if((self.__ds[iteration][s] >= (self.__yp[iteration][s] - self.__yn[iteration][s]))):
                self.__ds[iteration][s] = self.__ds[iteration][s] - \
                    (self.__yp[iteration][s] - self.__yn[iteration][s])
            # elif((self.__yn[iteration][s] - self.__yp[iteration][s]) > self.__cp[s] - self.__ds[iteration][s]):
            #     self.__ds[iteration][s] = self.__cp[s]
            else:
                self.__ds[iteration][s] = 0.0

        for s in range(self.nzones):
            for s1 in range(self.nzones):
                # if(self.__tfl1[iteration][s] <= self.__ds[iteration][s]):
                #     self.__xfl[iteration][k][s][s1] = self.__fl[iteration][k][s][s1]
                # else:
                if(self.__tfl1[iteration][s] > 0):
                    self.__xfl[iteration][s][s1] = min(self.__ds[iteration][s], sum(
                        self.__fl[iteration][s])) * (self.__fl[iteration][s][s1] / (self.__tfl1[iteration][s] * 1.0))

        for i in range(self.nzones):
            self.__ds[iteration + 1][i] = self.__ds[iteration][i] - \
                min(self.__ds[iteration][i], sum(self.__fl[iteration][i]))

        for z in range(self.nzones):
            for z1 in range(self.nzones):
                if(sum(self.__fl[iteration][z1]) > 0):
                    # (1.0*min(ds[iteration][z1],sum(fl[iteration][z1]))*fl[timstep][z1][z])/sum(fl[iteration][z1])
                    self.__ds[iteration + 1][z] = self.__ds[iteration + 1][z] + \
                        self.__xfl[iteration][z1][z]

        flag = 0

        while(flag == 0):
            for s in range(self.nzones):
                if(self.__ds[iteration + 1][s] > self.__cp[s]):
                    for s1 in self.__mindis[s]:
                        if((self.__ds[iteration + 1][s] - self.__cp[s]) <= (self.__cp[s1] - self.__ds[iteration + 1][s1])):
                            self.__ds[iteration + 1][s1] = self.__ds[iteration +
                                                                     1][s1] - self.__cp[s] + self.__ds[iteration + 1][s]
                            full_lost += self.__ds[iteration +
                                                   1][s] - self.__cp[s]
                            self.__ds[iteration + 1][s] = self.__cp[s]
                            break
                        elif(((self.__cp[s1] - self.__ds[iteration + 1][s1]) > 0) and ((self.__ds[iteration + 1][s] - self.__cp[s]) > (self.__cp[s1] - self.__ds[iteration + 1][s1]))):
                            self.__ds[iteration + 1][s] = self.__ds[iteration + 1][s] - \
                                (self.__cp[s1] - self.__ds[iteration + 1][s1])
                            full_lost += self.__cp[s1] - \
                                self.__ds[iteration + 1][s1]
                            self.__ds[iteration + 1][s1] = self.__cp[s1]

            flag = 1
            for s in range(self.nzones):
                if(self.__ds[iteration + 1][s] > self.__cp[s]):
                    print("I am stuck")

        lost_call = 0
        revenue = 0
        for s in range(self.nzones):
            for s1 in range(self.nzones):
                revenue += self.__xfl[iteration][s][s1]
                lost_call += self.__fl[iteration][s][s1] - \
                    self.__xfl[iteration][s][s1]

        return lost_call, full_lost, revenue

    def step(self, action):
        # modify yp and yn here according to action
        self.__set_yp_yn_from_action(action)
        lost_demand, full_lost_demand, revenue = self.__calculate_lost_demand_new_allocation()
        r = -(lost_demand + full_lost_demand)
        self.__t += 1
        done = self.__t >= self.ntimesteps
        return self._get_observation(), r, done, {"lost_demand_pickup": lost_demand, "lost_demand_dropoff": full_lost_demand, "revenue": revenue, "scenario": self._scenario}

    def render(self, mode='human', close=False):
        if not close:
            raise NotImplementedError(
                "This environment does not support rendering")