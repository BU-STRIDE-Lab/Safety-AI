from car import car
from grid import grid

from cvxopt import matrix, solvers

import numpy as np
import matplotlib
import pylab
import sys
from update import train


if __name__ == "__main__":
	grids= grid(8, 8, False, [[3, 7],[1, 6],[1, 3],[6, 5]], 0.7, sink = False)
	trains= train(grids= grids, gamma = 0.99, iteration = 20, starts = [grids.states[0][0]], steps = None, epsilon = 0.0001, theta = [1.0, 1.0, -10.0, 0.0])
	real=raw_input("Try synthesizing? [Y/N]")
	if real == 'Y' or real == 'y':
		#grids= grid(8, 8, False, [[4, 3], [1, 2], [1, 1], [4, 4]], 0.7, sink = False)
		#trains = train(grids = grids, gamma = 0.99, iteration = 20, starts = [grids.states[0][0]], steps = None, epsilon = 0.0001, theta = [ 1.0, 1.0, -1.0, 0.0])
		#starts = [np.array([0, 0])]
		trains.synthesize(theta = [1.0, 0.5, -1.0, 0.0], starts = starts)
		#grids = None
		#trains = None
	real=raw_input("Learn from optimal policy?[Y/N]")
	if real == 'Y' or real == 'y':
		#grids = grid_0
		#trains = train(grids = grids, gamma = 0.99, iteration = 20, starts = [grids.states[0][0]], steps = None, epsilon = 0.0001, theta = [1.0, 0.5, -1.0, 0.0])
		print "Start real optimal policy..."
		policy = trains.real_expert_train()
		print policy

	real=raw_input("Learn from human policy?[Y/N]")
	if real == 'Y' or real == 'y':
		#grids= grid(8, 8, False, [[4, 3], [1, 2], [1, 1], [4, 4]], 0.7, sink = False)
		#grids = grid_0
		#trains = train(grids = grids, gamma = 0.99, iteration = 20, starts = [grids.states[0][0]], steps = None, epsilon = 0.0001, theta = [ 1.0, 0.5, -1.0, 0.0])
		'''
		policy[grids.loc_min_0[0]-1, grids.loc_min_0[1]] = 1
		policy[grids.loc_min_0[0], grids.loc_min_0[1]-1] = 2
		policy[grids.loc_min_0[0]+1, grids.loc_min_0[1]] = 1
		#policy[grids.loc_min_0[0], grids.loc_min_0[1]+1] = 1
		policy[grids.loc_min_0[0]+1, grids.loc_min_0[1]+1] = 2
		#policy[grids.loc_min_0[0]-1, grids.loc_min_0[1]+1] = 1
		policy[grids.loc_min_0[0]+1, grids.loc_min_0[1]-1] = 2
		#policy[grids.loc_min_0[0]+2, grids.loc_min_0[1]] = 3
		policy= np.array([[1.0, 1.0, 1.0, 1.0, 1.0, 2.0, 2.0, 2.0] , 
				  [1.0, 2.0, 1.0, 1.0, 1.0, 1.0, 0.0, 3.0] , 
				  [1.0, 2.0, 2.0, 1.0, 1.0, 1.0, 4.0, 2.0] , 
     				  [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0] , 
				  [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 4.0] , 
				  [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 4.0, 4.0] , 
				  [1.0, 1.0, 1.0, 1.0, 4.0, 4.0, 4.0, 4.0] , 
				  [1.0, 1.0, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0] , 
				])

		print "learn form policy"	
		'''
		policy=trains.learn_from_policy()
		print policy
		
		#grids = None
		#trains = None
		
	
	real=raw_input("Try real expert training with random initial state and random features? [Y/N]")
	if real == 'Y' or real == 'y':
		for i in range(100):
			print "experiment ", i
			grids_1= grid(8, 8, True, 0.7, sink = True)
			trains_1 = train(grids = grids, gamma = 0.99, iteration = 20, starts = [grids.states[0][0]], steps = None, epsilon = 0.0001, theta = [1.0, 0.5, -1.0, 0.0])
			print "Start real expert training..."
			starts3 = [np.array([0, 0])]
			trains_1.real_expert_train(starts3, distribution=None, safety=True)
			grids_1 = None
			trains_1 = None
		
	
	real=raw_input("Try human demo? [Y/N]")
	if real == 'Y' or real == 'y':
		#grids= grid(8, 8, False, [[7, 7], [3, 3], [5, 5], [4, 4]], 0.7, sink = False)
		#grids = grid_0
		#trains = train(grids = grids, gamma = 0.99, iteration = 30, starts = [grids.states[0][0]], steps = None, epsilon = 0.0001, theta = [ 1.0, 0.5, -1.0, 0.0])
		policy_temp = trains.human_train()
		grids = None
		trains = None
	
	real=raw_input("Try real expert training with random optimal policy? [Y/N]")
	if real == 'Y' or real == 'y':
		distribution = []
		for i in range(11):
			distribution.append(1.0-i/10.0)
		#grids= grid(8, 8, False, [[7, 7], [3, 3], [5, 5], [4, 4]], 0.7,sink = True)
		#grids = grid_0
		#trains = train(grids = grids, gamma = 0.99, iteration = 20, starts = [grids.states[0][0]], steps = None, epsilon = 0.0001, theta = [1.0, 0.5, -1.0, 0.0])
		print "Start random expert optimal training..."
		starts3 = [np.array([0, 0])]
		trains.real_expert_train(starts3, distribution=distribution)
		#grids = None
		#trains = None

