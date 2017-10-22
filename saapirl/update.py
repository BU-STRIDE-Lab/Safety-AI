import time
from car import car
from grid_v2 import grid
import MDP
from cvxopt import matrix, solvers
import os
import numpy as np
import matplotlib
import pylab
import warnings
import random
import re
import subprocess, shlex
from threading import Timer
import math
warnings.filterwarnings("ignore")

def real_optimal(grids, agent, starts, steps, theta = None, gamma=0.5, epsilon = 1e-5):
	expert=[]
	if theta is None:
		#theta = np.array([1./3., 1./3., -3./3., 0.0])
		theta = np.random.randint(100, size = len(grids.features[-1][-1]))
	theta = theta/np.linalg.norm(theta, ord=2)
	grids.w_features(theta)
	#optimal_policy= update_policy(grids, steps= steps, epsilon= epsilon, gamma= gamma)
	optimal_policy, _ = optimal_value(grids, agent, steps= steps, epsilon= epsilon, gamma= gamma)
	print "real optimal policy generated"
	print "["
	for i in range(len(optimal_policy)):
		temp = []
		for j in range(len(optimal_policy[i])):
			temp.append(optimal_policy[i, j])
		print temp, ", "
	print "]" 
	#print optimal_policy
	file = open('optimal_policy', 'w')
	for i in optimal_policy:
		for j in i:
			file.write(str(j)+":")
		file.write("\n")
	file.close()

	opt_u, _  = optimal_feature(grids, starts, steps, optimal_policy, epsilon, gamma)
	return optimal_policy, opt_u
	


def demo(grids, agent, start, steps, theta = None, gamma=0.5, epsilon = 1e-5):
	expert={}
	agent.state=np.array(grids.states[start[0], start[1]])
	if theta is  None:
		theta = np.random.randint(100, size = len(grids.features[-1][-1]))
	theta = np.array(theta).astype(float)/np.linalg.norm(theta, ord=2)
		#theta=np.array([1./3., 1./3., -3./3., 0.0])
	trajectory=[{"state":agent.state, "feature": grids.features[agent.state[0]][agent.state[1]]}]
	grids.w_features(theta)
	pylab.close()
	pylab.ion()
	pylab.title("Generate demonstration[0:end, 1: left, 2: down, 3: right, 4: up]")
	draw_grids(grids.rewards, trajectory)
	print grids.rewards
	mu=np.zeros(len(grids.features[-1][-1]))
	action = grids.actions
	while(steps > 0 and action != 0):
		try:
			action = input("%0.0f steps left, action is " % steps)
			if steps == float("inf") and action == 0:
				pylab.ioff()
				pylab.close('all')
				break
			steps = steps - 1	
			if action!= 0 and action != 1 and action !=2 and action !=3 and action !=4:
				print("Invalid action, input again")
				next
			else:
				trajectory[-1]["action"]=action
				trajectory.append({"state": agent.move(grids.transitions, action)})
				trajectory[-1]["feature"]=np.array(grids.features[trajectory[-1]["state"][0]][trajectory[-1]["state"][1]])
				grids.w_features(theta)
				draw_grids(grids.rewards, trajectory)
		except:
			print("Invalid action, input again")
			next

	for i in range(len(trajectory)):
		mu = mu + (gamma**i) * trajectory[i]["feature"]
	diff = float("inf")
	while diff > epsilon:
		i = i + 1
		diff =  (gamma**i) * trajectory[-1]["feature"]
		mu = mu + diff
		diff = np.linalg.norm(diff, ord = 2)
		
	expert["mu"]=mu
	expert["trajectory"]=trajectory
 	playagain=raw_input("Want to play again? [y/n]?")
	return expert, playagain
	
def calc_u(grids, agent, policy, steps, gamma=0.5):
	mu=np.zeros(len(grids.features[-1][-1]))
	trajectory=[{"state":agent.state, "feature": grids.features[agent.state[0]][agent.state[1]]}]
	for i in range(steps):
		action=policy[agent.state[0], agent.state[1]]
		trajectory[-1]["action"]=action
		trajectory.append({"state": agent.move(grids.transitions, action)})
		trajectory[-1]["feature"]=np.array(grids.features[trajectory[-1]["state"][0]][trajectory[-1]["state"][1]])
	for i in range(len(trajectory)):
		mu = mu + (gamma**i) * trajectory[i]["feature"]
	return mu, trajectory

def exp_u(grids, agent, policy, start, start_action=None, steps=None, epoch=1000, gamma=0.5):
	if steps is None:
		steps = epoch
	mu=np.zeros(len(grids.features[-1][-1]))
	agent.state=np.array([start[0], start[1]])
	trajectory_i_j={}
	for i in range(epoch):
		if start_action is not None:
			org_action=policy[agent.state[0], agent.state[1]]
			policy[agent.state[0], agent.state[1]]=start_action
			mu_i_j_1, _= calc_u(grids, agent, policy , steps=1)
			policy[agent.state[0], agent.state[1]]=org_action
		else:
			mu_i_j_1 = np.zeros(len(grids.features[-1][-1]))
		mu_i_j, _ =calc_u(grids, agent, policy, steps=steps)
		mu = mu + mu_i_j + mu_i_j_1
		#	draw(rewards, trajectory)
	mu=mu/epoch
	return mu


def draw_grids(rewards, trajectory):
	pylab.set_cmap('gray')
	pylab.axis([0,len(rewards[0]), len(rewards),0])
	c = pylab.pcolor(rewards, edgecolors='w', linewidths=1)
	
	x=[]
	y=[]
	if trajectory!=None:
		for i in trajectory:
			y.append(i["state"][0])
			x.append(i["state"][1])
			pylab.plot(x, y, 'bo', x, y, 'b-', [x[-1]], [y[-1]], 'ro')
	pylab.show()

	


def sample_feature(grids, agent, starts, STEP, policy, epochs = 2000, epsilon = 1e-5, gamma = 0.5, bounds = None, unsafe = []):
	u =  np.zeros([len(grids.features), len(grids.features[-1]), len(grids.features[-1][-1])])
	u_G = np.zeros([len(grids.features), len(grids.features[-1]), len(grids.features[-1][-1])])
	u_B = np.zeros([len(grids.features), len(grids.features[-1]), len(grids.features[-1][-1])])
	p_B = np.zeros([len(grids.features), len(grids.features[-1])])
	p_G = np.zeros([len(grids.features), len(grids.features[-1])])
	B = np.zeros([len(grids.features), len(grids.features[-1]), 2])
	P = np.zeros([len(grids.features), len(grids.features[-1])])
	if STEP is None:
		STEP = grids.x_max * grids.y_max
	if bounds is None or True:
		bounds = []
		for start in range(len(starts)):
			bounds.append(STEP+1)

	for start in range(len(starts)):
	 	epochs_G=0.0
	 	epochs_B=0.0
 	 	while epochs_G + epochs_B <= epochs-1:
			agent.state = np.array(starts[start])
			path = [np.array(agent.state)]
			u_epoch = grids.features[agent.state[0]][agent.state[1]] 
			steps = 0
			end = False
			fail = False
			while steps < STEP and end is False:
				steps = steps + 1
				action_epoch = int(policy[agent.state[0], agent.state[1]])
				if fail is not True:
					agent.state = np.array(agent.move(grids.transitions, action_epoch))
					path.append(np.array(agent.state))
				if steps <= bounds[start]:
					for state in unsafe:
						if agent.state[0] ==  state[0] and agent.state[1] == state[1]:
							fail = True
							end = False
				u_epoch = u_epoch + grids.features[agent.state[0]][agent.state[1]] * (gamma**steps)
				if gamma**steps <= epsilon:
					end = True
			if fail is True:
				for state in path:
					B[state[0]][state[1]][0] = B[state[0]][state[1]][0] + 1
					B[state[0]][state[1]][1] = B[state[0]][state[1]][1] + 1
				u_B[starts[start][0], starts[start][1]] = u_B[starts[start][0], starts[start][1]]  + u_epoch
				epochs_B=epochs_B+1
			else:							
				for state in path:
					B[state[0]][state[1]][0] = B[state[0]][state[1]][0] + 1
				u_G[starts[start][0], starts[start][1]]  = u_G[starts[start][0], starts[start][1]]  + u_epoch
				epochs_G=epochs_G+1
			if np.linalg.norm((u_B[starts[start][0], starts[start][1]]+u_G[starts[start][0], starts[start][1]])/(epochs_G+epochs_B), ord=2) <= epsilon and  epochs_G+epochs_B>=epochs/2:
				break
	
		u_B[starts[start][0], starts[start][1]]  = u_B[starts[start][0], starts[start][1]] /epochs_B
		u_G[starts[start][0], starts[start][1]]  = u_G[starts[start][0], starts[start][1]] /epochs_G
		if epochs_B <= 0.0:
			u_B[starts[start][0], starts[start][1]] =np.zeros(len(grids.features[-1][-1]))
		if epochs_G <= 0.0:
			u_G[starts[start][0], starts[start][1]] =np.zeros(len(grids.features[-1][-1]))
		p_B[starts[start][0], starts[start][1]]  = float(epochs_B/(epochs_B+epochs_G))/len(starts)
  		p_G[starts[start][0], starts[start][1]]  = float(epochs_G/(epochs_B+epochs_G))/len(starts)
		
		
		for i in range(len(B)):
			for j in range(len(B[i])):
				if B[i, j, 0] > 0:
					P[i, j] = float(B[i, j, 1]/B[i, j, 0])
	return u_G, p_G, u_B, p_B, P





def optimal_feature(grids, starts, steps, policy, epsilon = 1e-5, gamma= 0.5):
	exp_u= np.zeros(len(grids.features[-1][-1])).astype(float)
	features= np.array(grids.features)

	transitions_ = grids.pi_transitions(policy)
	print "Policy loaded..."
	diff = float("inf")
	while diff > epsilon:
		#print diff
		diff = -float('inf')
		features_temp = np.array(grids.features)
		for i in range(grids.y_max):
			for j in range(grids.x_max):
				transitions = np.reshape(np.repeat(transitions_[i, j], len(grids.features[-1][-1])), [grids.y_max, grids.x_max, len(grids.features[-1][-1])])
				
				features_temp[i, j] += np.sum(np.reshape(transitions * features, [grids.y_max * grids.x_max, len(grids.features[-1][-1])]), 0) * gamma	
				new_diff = np.linalg.norm(features[i, j] - features_temp[i, j], ord= 2)
				if new_diff > diff:
					diff = new_diff
		features=np.array(features_temp)
	'''
	transitions_ = grids.pi_transitions(policy)
	transitions = np.ones([grids.y_max, grids.x_max, grids.y_max, grids.x_max, len(grids.features[-1][-1])])
	for i in range(grids.y_max):
		for j in range(grids.x_max):
			for m in range(grids.y_max):
				for n in range(grids.x_max):
					transitions[i, j, m, n] *= transitions_[i, j, m, n]
	transitions_ = None
	print "Policy loaded..."
	diff = float("inf")
	while diff > epsilon:
		print diff
		diff = -float('inf')
		features_temp = np.array(grids.features)
		for i in range(grids.y_max):
			for j in range(grids.x_max):
				features_temp[i, j] += np.sum(np.reshape(transitions[i, j] * features, [grids.y_max * grids.x_max, len(grids.features[-1][-1])]), 0) * gamma	
				new_diff = np.linalg.norm(features[i, j] - features_temp[i, j], ord= 2)
				if new_diff > diff:
					diff = new_diff
		features=np.array(features_temp)


	if steps + 1 != steps:
		features_temp = np.array(grids.features)
		for i in range(grids.y_max):
			for j in range(grids.x_max):
				action = int(policy[i, j])
				transition = np.array(grids.transitions[i, j, action])
				for m in range(grids.y_max):
					for n in range(grids.x_max):
						features_temp[i, j] = features_temp[i, j] + np.multiply(transition[m, n], gamma * features[m][n])	
		features= np.array(features_temp)
	diff = float("inf")
	while diff > epsilon:
		print diff
		diff = -float('inf')
		features_temp = np.array(grids.features)
		for i in range(grids.y_max):
			for j in range(grids.x_max):
				action = int(policy[i, j])
				transition = np.array(grids.transitions[i, j, action])
				for m in range(grids.y_max):
					for n in range(grids.x_max):
						features_temp[i, j] = features_temp[i, j] + np.multiply(transition[m, n], gamma * features[m][n])	
				new_diff = np.linalg.norm(features[i, j] - features_temp[i, j], ord= 2)
				if new_diff > diff:
					diff = new_diff
		features=np.array(features_temp)
	'''	
	for i in range(len(starts)):
		exp_u = exp_u + features[starts[i][0]][starts[i][1]]
	exp_u = exp_u/len(starts)
	return exp_u, features



def optimal_value(grids, agent, steps, epsilon = 1e-5, gamma = 0.5, toolbox = False, starts = [[0, 0]], epoch = 1000):
	values = np.array(grids.rewards)
	policy = np.zeros([grids.y_max, grids.x_max])
	if toolbox is True:
		S = grids.y_max * grids.x_max
		A = grids.actions
		exp = MDP.SparseExperience(S, A);
		model = MDP.SparseRLModel(exp, gamma);
		solver = MDP.PrioritizedSweepingSparseRLModel(model, 0.1, 500);
		action = MDP.QSoftmaxPolicy(solver.getQFunction(), 10.0 / 121);

		for i_episode in xrange(epoch):
			o = grids.states[starts[0][0], starts[0][1]]
			for t in xrange(steps):
       			# Convert the observation into our own space
     		   	# Select the best action according to the policy
   				s = o[0] * grids.x_max + o[1]
        			a = action.sampleAction(s)
        		# Act
				o1 = np.array(agent.move(grids.transitions, a))
        		# See where we arrived
   				s1 = o1[0] * grids.x_max + o1[1]

        # Record information, and then run PrioritizedSweeping
        			exp.record(s, a, s1, grids.rewards[o[0], o[1]]);
        			model.sync(s, a, s1);
        			solver.stepUpdateQ(s, a);
        			solver.batchUpdateQ();

        			o = o1;
		for s in xrange(S):
			policy[int(s/grids.x_max), int(s%grids.x_max)] = action.sampleAction(s)
		return policy, values

	'''	
	diff = float("inf")
	while diff > epsilon:
		print diff
		if diff != float("inf") and diff > 1.0/epsilon:
			print "Error: value exploded!!!!!!!!!!!!!!"
			return None
		diff = 0.
		values_temp = np.zeros([grids.y_max, grids.x_max]).astype(float)
		values_transitions = np.multiply(grids.transitions, values).astype(float)
			
		values_transitions = np.reshape(values_transitions, [grids.y_max, grids.x_max, grids.actions, grids.y_max * grids.x_max])
		values_ = np.zeros([grids.y_max, grids.x_max, grids.actions])
		for i in range(grids.y_max):
			for j in range(grids.x_max):
				for k in range(grids.actions):
					values_[i, j, k] = np.sum(values_transitions[i, j, k])
				policy[i, j] = np.argmax(values_[i, j])
				values_temp[i, j] = grids.rewards[i, j]+ gamma * values_[i, j, int(policy[i, j])]
				new_diff = abs(values[i, j] - values_temp[i, j])
				if new_diff >  diff:
					diff = new_diff
		#values = np.array(values + 0.1 * (values_temp - values))
		values = np.array(values_temp)	
	return policy, values
	'''
	diff = float("inf")
	while diff > epsilon:
		#print diff
		if diff != float("inf") and diff > 1.0/epsilon:
			print "Error: value exploded!!!!!!!!!!!!!!"
			return None
		diff = 0.
		values_temp = np.zeros([grids.y_max, grids.x_max])
		for i in range(grids.y_max):
			for j in range(grids.x_max):
				max_value = float("-inf")
				for k in range(grids.actions):
					transition_k = grids.transitions[i, j, k]
					reward_k = np.multiply(transition_k, values)
					'''
					value_k = 0.
					for m in range(grids.y_max):
						for n in range(grids.x_max):
							value_k+= reward_k[m, n]
					'''
					value_k = np.sum(np.reshape(reward_k,[grids.y_max*grids.x_max]))
					if max_value < value_k:
						policy[i, j] = k
						max_value = value_k
				values_temp[i, j] = grids.rewards[i, j] + gamma * max_value
				new_diff = abs(values[i, j] - values_temp[i, j])
				if new_diff >  diff:
					diff = new_diff
		#values = np.array(values + 0.1 * (values_temp - values))
		values = np.array(values_temp)	
	return policy, values

#def update_policy(grids, steps, epsilon= 1e-5, gamma=0.5):	
#	policy=np.ones([grids.y_max, grids.x_max])
#	policy, values = optimal_value(grids, agent, steps= steps-1, epsilon=epsilon, gamma=gamma)
#	Q = np.zeros([grids.x_max, grids.y_max, 5])
#	for i in range(grids.y_max):
#		for j in range(grids.x_max):
#			for k in range(5):
#				value_k= grids.rewards[i, j]
#				transition_k = grids.transitions[i, j, k]
#				reward_k = np.multiply(transition_k, gamma * values)
#				for m in range(grids.y_max):
#					for n in range(grids.x_max):
#						value_k+= reward_k[m, n]
#				Q[i, j, k] = value_k
#			policy[i, j] = np.argmax(Q[i, j])
#	return policy

def update_policy(grids, values, epsilon= 1e-5, gamma=0.5):	
	policy=np.ones([grids.y_max, grids.x_max])
	Q = np.zeros([grids.x_max, grids.y_max, grids.actions])
	for i in range(grids.y_max):
		for j in range(grids.x_max):
			for k in range(grids.actions):
				value_k= grids.rewards[i, j]
				transition_k = grids.transitions[i, j, k]
				reward_k = np.multiply(transition_k, gamma * values)
				for m in range(grids.y_max):
					for n in range(grids.x_max):
						value_k+= reward_k[m, n]
				Q[i, j, k] = value_k
			policy[i, j] = np.argmax(Q[i, j])
	return policy




def expert_train(grids, expert, agent, starts, steps, epsilon=1e-6, iteration=100, gamma=0.5, start_theta= None, MC = False, safety = None, unsafe = None, toolbox = False):
	if start_theta is None:
		start_theta=np.random.randint(-100, 100, len(grids.features[-1][-1]))
	if safety is None:
		bounds = np.zeros([len(starts)])
	new_theta=start_theta/np.linalg.norm(start_theta, ord=2)
	print "Initial theta ", new_theta
	grids.w_features(new_theta)
	thetas = [new_theta]
	new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma, toolbox = toolbox, starts = starts)
	policies = [new_policy]
	values = [new_value]
	if MC is False:
		new_mu, _ = optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
	else:
		exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = 1e-3, gamma=gamma, bounds = bounds, unsafe = unsafe)
		new_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 

	print "Initial expected features ", new_mu
	#print "Initial expected feature error ", np.linalg.norm(expert-new_mu, ord=2)
	mus = [new_mu]
	flag = float("inf")
	new_index = 0
	index = 0
	
	for i in range(iteration):
		new_index, new_theta, w_delta_mu = expert_update_theta(grids, expert, agent, steps, policies, mus, gamma, epsilon)
		new_theta = new_theta/np.linalg.norm(new_theta, ord=2)	
		print i, " iteration", "policy ", new_index, " weighted delta mu: ", w_delta_mu, "new theta: ", new_theta 
	
		print "start learning...."
		grids.w_features(new_theta)
		#if weighted weighted feature approximates the expert, end training
		new_policy, new_value  = optimal_value(grids, agent, steps = steps, epsilon= epsilon, gamma = gamma, toolbox = toolbox, starts = starts)
		'''
		file = open('log', 'a')
		file.write(str(new_theta)+'\n')
		for i in range(len(new_policy)):
			for j in range(len(new_policy[i])):
				file.write(str(new_policy[i, j]) + ':')
			file.write('\n')
		file.write('\n')
		file.close()
		'''
		print "new policy generated...begin next iteration"
		if MC is False:
			new_mu, _ =  optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
		else:
			exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = 1e-3, gamma=gamma, bounds = bounds, unsafe = unsafe)
			new_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 

		thetas.append(new_theta)
		policies.append(new_policy)
		values.append(new_value)
		mus.append(new_mu)
		print "new policy expected feature", new_mu
		print "new policy expected feature error ", np.linalg.norm(expert-new_mu, ord=2)
		if np.linalg.norm(expert-new_mu, ord=2) < np.linalg.norm(expert-mus[index], ord=2):
			index = len(mus)-1
			print "policy ", index, " is the new best learnt policy"
			if safety is not None:
				exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, policies[index], epochs= 5000, epsilon = epsilon, gamma=gamma, bounds = bounds, unsafe= unsafe)
				p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))
				print "best policy's unsafe rate ", p_B_sum
				if p_B_sum > safety:
					mus[index] = mus[index] -  (p_B_sum - safety) * np.sum(np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0)
				print "feature counts modified to ", mus[index]

				
		if abs(w_delta_mu) < epsilon:
			print "|expert_w_mu - w_mu| = ", abs(w_delta_mu), " < ", epsilon
			#index = new_index
			break	

		if np.linalg.norm(mus[-1]-mus[-2], ord=2)<=epsilon and np.linalg.norm(thetas[-1]-thetas[-2], ord=2)<=epsilon:
			print "Difference with last iteration is too small"
			break	
	#index = -1
	#print "best policy"
	#print policies[index]
	print "best weight", thetas[index]
	print "best feature", mus[index]
	print "best policy\n", policies[index]
	grids.w_features(thetas[index])
	#draw_grids(grids.rewards, None)
	return grids, thetas[index], policies[index], values[index]


def expert_train_v1(grids, experts, agent, starts, steps, epsilon=1e-6, iteration=100, gamma=0.5, start_theta= None, MC = False, safety = None):
	if start_theta is None:
		start_theta=np.random.randint(-100, 100, len(grids.features[-1][-1]))
	new_theta=start_theta/np.linalg.norm(start_theta, ord=2)
	expert = np.zeros(len(grids.features[-1][-1]))
	grids.w_features(new_theta)
	thetas = [new_theta]
	new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)
	policies = [new_policy]
	values = [new_value]
	if MC is False:
		new_mu = optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
	else:
		exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 1000, epsilon = 1e-3, gamma=gamma)
		new_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]), 0)
		## +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 

	print "Initial theta ", new_theta
	print "Initial expected features ", new_mu
	print "Initial expected feature error ", np.linalg.norm(expert-new_mu, ord=2)
	mus = [new_mu]
	flag = float("inf")
	new_index = 0
	index = 0
	
	for i in range(iteration):
		new_index, new_theta, w_delta_mu = expert_update_theta_v1(grids, experts, agent, steps, policies, mus, gamma, epsilon)
		new_theta = new_theta/np.linalg.norm(new_theta, ord=2)	
		print i, " iteration", "[CEX, expert, policy] = ", new_index, " weighted delta mu: ", w_delta_mu, "new theta: ", new_theta 
		
		expert = np.zeros(len(grids.features[-1][-1]))
		for i in range(len(new_index)-1):
			expert = expert + experts[0][i] * experts[1][i][new_index[i]]
		print "Combinatorial expert feature ", expert
	
		print "start learning...."
		grids.w_features(new_theta)
		#if weighted weighted feature approximates the expert, end training
		new_policy, new_value  = optimal_value(grids, agent, steps = steps, epsilon= epsilon, gamma = gamma)
		print "new policy generated...begin next iteration"
		if MC is False:
			new_mu =  optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
		else:
			exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 1000, epsilon = 1e-3, gamma=gamma)
			new_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 

		thetas.append(new_theta)
		policies.append(new_policy)
		values.append(new_value)
		mus.append(new_mu)
		print "new policy expected feature", new_mu
		print "new policy expected feature error ", np.linalg.norm(expert-new_mu, ord=2)
		if np.linalg.norm(expert-new_mu, ord=2) < flag:
			index = len(mus)-1
			flag = np.linalg.norm(expert-new_mu, ord=2)
			print "policy ", index, " is the new best learnt policy"
			if safety is not None:
				exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, policies[index], epochs= 5000, epsilon = epsilon, gamma=gamma)
				p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))
				print "best policy's unsafe rate ", p_B_sum
				if p_B_sum > safety:
					mus[index] = mus[index] -  (p_B_sum - safety) * np.sum(np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0)
				print "feature counts modified to ", mus[index]

		else:
			print "policy ", index, " is still the best learnt policy"	
		if abs(w_delta_mu) < epsilon:
			print "|expert_w_mu - w_mu| = ", abs(w_delta_mu), " < ", epsilon
			index = new_index[-1]
			print "policy ", index, " is the new best learnt policy"
			break	
		
		if np.linalg.norm(mus[-1]-mus[-2], ord=2)<=epsilon and np.linalg.norm(thetas[-1]-thetas[-2], ord=2)<=epsilon:
			print "Difference with last iteration is too small"
			print "policy ", index, " is the new best learnt policy"
			break	
	#index = -1
	#print "best policy"
	#print policies[index]
	print "best weight", thetas[index]
	print "best feature", mus[index]
	print "best policy\n", policies[index]	
	grids.w_features(thetas[index])
	#draw_grids(grids.rewards, None)
	return grids, thetas[index], policies[index], values[index]
def expert_update_theta(grids, expert, agent, steps, policies, mus, gamma=0.5, epsilon = 1e-5):
	#mus=[]
	delta_mus = []
	w_delta_mus=[]
	solutions=[]
	exp_mu = expert
	#for policy in policies:
	#	mu = optimal_feature(grids, steps, policy, epsilon = epsilon, gamma=gamma)
	#	mus.append(mu)
		
	for i in range(len(mus)):
		#G_i=[[], [], [], []]
		G_i = []
		h_i = []
		
		for k in range(len(mus[i])):
			G_i.append([- (exp_mu[k] - mus[i][k])])	
		#G_i = [[- (exp_mu[0] - mus[i][0])],
		#	[- (exp_mu[1] - mus[i][1])],
		#	[- (exp_mu[2] - mus[i][2])],
		#	[- (exp_mu[3] - mus[i][3])]
		#]
		h_i = [0]
		c = matrix(mus[i] - exp_mu)
		for j in range(len(mus)):
			for k in range(len(mus[i])):
				G_i[k].append(- mus[i][k] - (- mus[j][k]))	
			#G_i[0].append(-1 * mus[i][0] - (-1) * mus[j][0])
			#G_i[1].append(-1 * mus[i][1] - (-1) * mus[j][1])
			#G_i[2].append(-1 * mus[i][2] - (-1) * mus[j][2])
			#G_i[3].append(-1 * mus[i][3] - (-1) * mus[j][3])
			h_i.append(0)
		for k in range(len(mus[i])):
			G_i[k] = G_i[k] + [0.0] * (k + 1) + [-1.0] + [0.0] * (len(mus[i]) - k - 1)
		h_i = h_i + [1] + len(mus[i]) * [0.0]
		#G_i[0]= G_i[0] + [0., -1., 0., 0., 0.]
		#G_i[1]= G_i[1] + [0., 0., -1., 0., 0.]
		#G_i[2]= G_i[2] + [0., 0., 0., -1., 0.]
		#G_i[3]= G_i[3] + [0., 0., 0., 0., -1.]
		#h_i = h_i + [1., 0., 0., 0., 0.]

		G = matrix(G_i)
	#	h = matrix([-1 * penalty, 1., 0., 0., 0.])
		h = matrix(h_i)

		dims = {'l': 1 + len(mus), 'q': [len(mus[i]) + 1], 's': []}
		sol = solvers.conelp(c, G, h, dims)
		sol['status']
		solution = np.array(sol['x'])
		if solution is not None:
			solution=solution.reshape(len(mus[i]))
			w_delta_mu=np.dot(solution, exp_mu - mus[i])
			w_delta_mus.append(w_delta_mu)
		else:
			w_delta_mus.append(None)
		solutions.append(solution)
	index = np.argmax(w_delta_mus)
	
	#solution = delta_mus[index]/np.linalg.norm(delta_mus[index], ord =2)
	#delta_mu = np.linalg.norm(delta_mus[index], ord =2)  
	return index, solutions[index], w_delta_mus[index]


def expert_update_theta_v1(grids, agent, steps, policies, mus, mu_Bs, gamma=0.5, epsilon = 1e-5):
	delta_mus = []
	w_delta_mus=np.zeros([len(mus), len(mu_Bs)])
	solutions=np.zeros([len(mus), len(mu_Bs), len(grids.features[-1][-1])])
	indices = []
	index = [0, 0]
	max_w_delta_mus = -float('inf')
	for i in range(len(mus)):
		indices.append([])
		for j in range(len(mu_Bs)):
			c = matrix(- ( mus[i] - mu_Bs[j]))
			G_i_j = []
			h_i_j = []
			for e in range(len(grids.features[-1][-1])):
				G_i_j.append([])
				#G_i_j.append([- (mus[i][e] - mu_Bs[j][e])])
			#h_i_j.append(0)
			for m in range(len(mus)):
				for n in range(len(mu_Bs)):
					for e in range(len(grids.features[-1][-1])): 
						G_i_j[e].append(- (mus[m][e] - mu_Bs[n][e] - (mus[i][e] - mu_Bs[j][e])))
					h_i_j.append(0)
						#G_i_j[0].append(mus[k][0] - mu_Bs[j][0] - (mus[l][0] - mu_Bs[n][0]))
						#G_i_j[1].append(mus[k][1] - mu_Bs[j][1] - (mus[l][1] - mu_Bs[n][1]))
						#G_i_j[2].append(mus[k][2] - mu_Bs[j][2] - (mus[l][2] - mu_Bs[n][2]))
						#G_i_j[3].append(mus[k][3] - mu_Bs[j][3] - (mus[l][3] - mu_Bs[n][3]))
						#h_i_j.append(0)
				
			for e in range(len(grids.features[-1][-1])):
				G_i_j[e] = G_i_j[e] + [0.0] * (e + 1) + [-1.0] + [0.0] * (len(grids.features[-1][-1]) - e - 1)
			h_i_j = h_i_j + [1] + len(grids.features[-1][-1]) * [0.0]

				#G_i_j[0]= G_i_j[0] + [0., -1., 0., 0., 0.]
				#G_i_j[1]= G_i_j[1] + [0., 0., -1., 0., 0.]
				#G_i_j[2]= G_i_j[2] + [0., 0., 0., -1., 0.]
				#G_i_j[3]= G_i_j[3] + [0., 0., 0., 0., -1.]
				#h_i_j = h_i_j + [1., 0., 0., 0., 0.]
			G = matrix(G_i_j)
			h = matrix(h_i_j)
			#G = matrix(G_i_j)
			#h = matrix([-1 * penalty, 1., 0., 0., 0.])
			#h = matrix(h_i_j)
			dims = {'l':  len(mu_Bs) * len(mus), 'q': [1 + len(grids.features[-1][-1])], 's': []}
			sol = solvers.conelp(c, G, h, dims)
			sol['status']
			solution = np.array(sol['x'])
			if solution is not None:
				solution=solution.reshape([len(grids.features[-1][-1])])
				w_delta_mus[i][j]=np.dot(solution, mus[i] - mu_Bs[j])
			else:
				w_delta_mus[i][j] = None
			solutions[i][j] = solution/np.linalg.norm(solution, ord=2)
		indices[i].append(np.argmax(w_delta_mus[i]))
		if w_delta_mus[i][indices[i]] > max_w_delta_mus:
			max_w_delta_mus = w_delta_mus[i][indices[i]]
			index = [i, indices[i]]
	return index, solutions[index[0]][index[1]], w_delta_mus[index[0]][index[1]]

def expert_update_theta_v2(grids, experts, agent, steps, policies, mus, gamma=0.5, epsilon = 1e-5, safety = None):
	mu = np.zeros(len(grids.features[-1][-1]))
	mu_B = np.zeros(len(grids.features[-1][-1]))

	mu_Bs = []
	for i in experts[1][0]:
		mu_Bs.append(i)
	
	delta_mus = []
	w_delta_mus=np.zeros([len(mus), len(mu_Bs), len(mus)])
	solutions=np.zeros([len(mus), len(mu_Bs), len(mus), len(mus[0])])
	exp_mu = experts[-1][-1][-1]
	indices = []
	index = [0, 0, 0]
	safety = experts[0][0]
	max_w_delta_mus = -float('inf')
	for i in range(len(mus)):
		indices.append([])
		for j in range(len(mu_Bs)):
			for k in range(len(mus)):
				#G_i_j=[[], [], [], []]
				G_i_j_k = []
				for e in range(len(mus[k])):
					G_i_j_k.append([])
				h_i_j_k = []
				c = matrix(- ((1 - safety) * (exp_mu  -  mus[i]) + safety * (mus[k]- mu_Bs[j])))

				#G_i_j = [[- (exp_mu[0] - mus[i][0])],
				#	 [- (exp_mu[1] - mus[i][1])],
				#	 [- (exp_mu[2] - mus[i][2])],
				#	 [- (exp_mu[3] - mus[i][3])]
				#	]
				#h_i_j = [0]

				#G_i_j[0].append(- (mus[j][0] - mu_Bs[i][0]))
				#G_i_j[1].append(- (mus[j][1] - mu_Bs[i][0]))
				#G_i_j[2].append(- (mus[j][2] - mu_Bs[i][0]))
				#G_i_j[3].append(- (mus[j][3] - mu_Bs[i][0]))
				#h_i_j.append(0)
			
						
				#G_i_j[0].append(- ((1 - safety) * (exp_mu[0] - mus[i][0]) + safety * (mus[i][0] - mu_Bs[j][0])))
				#G_i_j[1].append(- ((1 - safety) * (exp_mu[1] - mus[i][1]) + safety * (mus[i][1] - mu_Bs[j][1])))
				#G_i_j[2].append(- ((1 - safety) * (exp_mu[2] - mus[i][2]) + safety * (mus[i][2] - mu_Bs[j][2])))
				#G_i_j[3].append(- ((1 - safety) * (exp_mu[3] - mus[i][3]) + safety * (mus[i][3] - mu_Bs[j][3])))
				#h_i_j.append(0)

			#	for m in range(len(mus)):
			#		for n in range(len(mu_Bs)):
			#			for l in range(len(mus)):
			#				G_i_j[0].append(safety * mus[k][0] - safety * mu_Bs[j][0] - (1 - safety) * mus[i][0] - ( - (1 - safety) * mus[m][0] + safety * mus[l][0] - safety * mu_Bs[n][0]))
			#				G_i_j[1].append(safety * mus[k][1] - safety * mu_Bs[j][1] - (1 - safety) * mus[i][1] - ( - (1 - safety) * mus[m][1] + safety * mus[l][0] - safety * mu_Bs[n][1]))
			#				G_i_j[2].append(safety * mus[k][2] - safety * mu_Bs[j][2] - (1 - safety) * mus[i][2] - ( - (1 - safety) * mus[m][2] + safety * mus[l][0] - safety * mu_Bs[n][2]))
			#				G_i_j[3].append(safety * mus[k][3] - safety * mu_Bs[j][3] - (1 - safety) * mus[i][3] - ( - (1 - safety) * mus[m][3] + safety * mus[l][0] - safety * mu_Bs[n][3]))
			#				h_i_j.append(0)

				for m in range(len(mus)):
					for e in range(len(mus[m])):
						G_i_j_k[e].append(- (1 - safety) * (exp_mu[e] - mus[m][e]))
					h_i_j_k.append(0)
					#G_i_j[0].append(- (exp_mu[0] - mus[m][0]))
					#G_i_j[1].append(- (exp_mu[1] - mus[m][1]))
					#G_i_j[2].append(- (exp_mu[2] - mus[m][2]))
					#G_i_j[3].append(- (exp_mu[3] - mus[m][3]))
					#h_i_j.append(0)
				
			
						
				for n in range(len(mu_Bs)):
					for l in range(len(mus)):
						for e in range(len(mus[l])):
							G_i_j_k[e].append(safety * (mus[k][e] - mu_Bs[j][e] - (mus[l][e] - mu_Bs[n][e])))
						h_i_j_k.append(0)
						#G_i_j[0].append(mus[k][0] - mu_Bs[j][0] - (mus[l][0] - mu_Bs[n][0]))
						#G_i_j[1].append(mus[k][1] - mu_Bs[j][1] - (mus[l][1] - mu_Bs[n][1]))
						#G_i_j[2].append(mus[k][2] - mu_Bs[j][2] - (mus[l][2] - mu_Bs[n][2]))
						#G_i_j[3].append(mus[k][3] - mu_Bs[j][3] - (mus[l][3] - mu_Bs[n][3]))
						#h_i_j.append(0)
				
				for e in range(len(mus[i])):
					G_i_j_k[e] = G_i_j_k[e] + [0.0] * (e + 1) + [-1.0] + [0.0] * (len(mus[i]) - e - 1)
				h_i_j_k = h_i_j_k + [1] + len(mus[i]) * [0.0]

				#G_i_j[0]= G_i_j[0] + [0., -1., 0., 0., 0.]
				#G_i_j[1]= G_i_j[1] + [0., 0., -1., 0., 0.]
				#G_i_j[2]= G_i_j[2] + [0., 0., 0., -1., 0.]
				#G_i_j[3]= G_i_j[3] + [0., 0., 0., 0., -1.]
				#h_i_j = h_i_j + [1., 0., 0., 0., 0.]
				G = matrix(G_i_j_k)
				h = matrix(h_i_j_k)
				#G = matrix(G_i_j)
			#	h = matrix([-1 * penalty, 1., 0., 0., 0.])
				#h = matrix(h_i_j)
				dims = {'l':  len(mus) + len(mu_Bs) * len(mus), 'q': [1 + len(mus[i])], 's': []}
				sol = solvers.conelp(c, G, h, dims)
				sol['status']
				solution = np.array(sol['x'])
				if solution is not None:
					solution=solution.reshape(len(mus[i]))
					w_delta_mu=np.dot(solution, (1 - safety) * (exp_mu - mus[i]) + safety * (mus[k] - mu_Bs[j]))
					w_delta_mus[i][j][k] = w_delta_mu
				else:
					w_delta_mus[i][j][k] = None
				solutions[i][j][k]=solution/np.linalg.norm(solution, ord=2)
			#indices[i].append(np.argmax(w_delta_mus[i][j]))
			#if w_delta_mus[i][j][indices[i][j]] > max_w_delta_mus:
			#	max_w_delta_mus = w_delta_mus[i][j][indices[i][j]]
			if w_delta_mus[i][j][np.argmax(w_delta_mus[i][j])] > max_w_delta_mus:
				max_w_delta_mus = w_delta_mus[i][j][np.argmax(w_delta_mus[i][j])]
				index = [np.argmax(w_delta_mus[i][j]), j, i]
	return index, solutions[index[-1]][index[-2]][index[0]], w_delta_mus[index[-1]][index[-2]][index[0]]


def expert_update_theta_v3(grids, experts, agent, steps, policies, MUS, gamma=0.5, epsilon = 1e-5, safety = None):
	mu = np.zeros(len(grids.features[-1][-1]))
	mu_b = np.zeros(len(grids.features[-1][-1]))
	mu_cex = np.zeros(len(grids.features[-1][-1]))

	mu_CEXs = []
	for i in experts[1][0]:
		mu_CEXs.append(i)
	
	mus = []
	for i in MUS[1]:
		mus.append(i)

	mu_Gs = []
	for i in MUS[0]:
		mu_Gs.append(i)
	
	delta_mus = []
	w_delta_mus=np.zeros([len(mus), len(mu_CEXs), len(mu_Gs)])
	solutions=np.zeros([len(mus), len(mu_CEXs), len(mu_Gs), len(mus[0])])
	exp_mu = experts[-1][-1][-1]
	indices = []
	index = [0, 0, 0]
	safety = experts[0][0]
	max_w_delta_mus = -float('inf')
	for i in range(len(mus)):
		indices.append([])
		for j in range(len(mu_CEXs)):
			for k in range(len(mu_Gs)):
				#G_i_j=[[], [], [], []]
				G_i_j_k = []
				for e in range(len(mus[i])):
					G_i_j_k.append([])
				h_i_j_k = []
				c = matrix(- ((1 - safety) * (exp_mu  -  mus[i]) + safety * (mu_Gs[k]- mu_CEXs[j])))

				#G_i_j = [[- (exp_mu[0] - mus[i][0])],
				#	 [- (exp_mu[1] - mus[i][1])],
				#	 [- (exp_mu[2] - mus[i][2])],
				#	 [- (exp_mu[3] - mus[i][3])]
				#	]
				#h_i_j = [0]

				#G_i_j[0].append(- (mus[j][0] - mu_Bs[i][0]))
				#G_i_j[1].append(- (mus[j][1] - mu_Bs[i][0]))
				#G_i_j[2].append(- (mus[j][2] - mu_Bs[i][0]))
				#G_i_j[3].append(- (mus[j][3] - mu_Bs[i][0]))
				#h_i_j.append(0)
			
						
				#G_i_j[0].append(- ((1 - safety) * (exp_mu[0] - mus[i][0]) + safety * (mus[i][0] - mu_Bs[j][0])))
				#G_i_j[1].append(- ((1 - safety) * (exp_mu[1] - mus[i][1]) + safety * (mus[i][1] - mu_Bs[j][1])))
				#G_i_j[2].append(- ((1 - safety) * (exp_mu[2] - mus[i][2]) + safety * (mus[i][2] - mu_Bs[j][2])))
				#G_i_j[3].append(- ((1 - safety) * (exp_mu[3] - mus[i][3]) + safety * (mus[i][3] - mu_Bs[j][3])))
				#h_i_j.append(0)

			#	for m in range(len(mus)):
			#		for n in range(len(mu_Bs)):
			#			for l in range(len(mus)):
			#				G_i_j[0].append(safety * mus[k][0] - safety * mu_Bs[j][0] - (1 - safety) * mus[i][0] - ( - (1 - safety) * mus[m][0] + safety * mus[l][0] - safety * mu_Bs[n][0]))
			#				G_i_j[1].append(safety * mus[k][1] - safety * mu_Bs[j][1] - (1 - safety) * mus[i][1] - ( - (1 - safety) * mus[m][1] + safety * mus[l][0] - safety * mu_Bs[n][1]))
			#				G_i_j[2].append(safety * mus[k][2] - safety * mu_Bs[j][2] - (1 - safety) * mus[i][2] - ( - (1 - safety) * mus[m][2] + safety * mus[l][0] - safety * mu_Bs[n][2]))
			#				G_i_j[3].append(safety * mus[k][3] - safety * mu_Bs[j][3] - (1 - safety) * mus[i][3] - ( - (1 - safety) * mus[m][3] + safety * mus[l][0] - safety * mu_Bs[n][3]))
			#				h_i_j.append(0)

				for m in range(len(mus)):
					for e in range(len(mus[m])):
						G_i_j_k[e].append(- (1 - safety) * (exp_mu[e] - mus[m][e]))
					h_i_j_k.append(0)
					#G_i_j[0].append(- (exp_mu[0] - mus[m][0]))
					#G_i_j[1].append(- (exp_mu[1] - mus[m][1]))
					#G_i_j[2].append(- (exp_mu[2] - mus[m][2]))
					#G_i_j[3].append(- (exp_mu[3] - mus[m][3]))
					#h_i_j.append(0)
				
			
						
				for n in range(len(mu_CEXs)):
					for l in range(len(mu_Gs)):
						for e in range(len(mu_Gs[l])):
							G_i_j_k[e].append(safety * (mu_Gs[k][e] - mu_CEXs[j][e] - (mu_Gs[l][e] - mu_CEXs[n][e])))
						h_i_j_k.append(0)
						#G_i_j[0].append(mus[k][0] - mu_Bs[j][0] - (mus[l][0] - mu_Bs[n][0]))
						#G_i_j[1].append(mus[k][1] - mu_Bs[j][1] - (mus[l][1] - mu_Bs[n][1]))
						#G_i_j[2].append(mus[k][2] - mu_Bs[j][2] - (mus[l][2] - mu_Bs[n][2]))
						#G_i_j[3].append(mus[k][3] - mu_Bs[j][3] - (mus[l][3] - mu_Bs[n][3]))
						#h_i_j.append(0)
				
				for e in range(len(mus[i])):
					G_i_j_k[e] = G_i_j_k[e] + [0.0] * (e + 1) + [-1.0] + [0.0] * (len(mus[i]) - e - 1)
				h_i_j_k = h_i_j_k + [1] + len(mus[i]) * [0.0]

				#G_i_j[0]= G_i_j[0] + [0., -1., 0., 0., 0.]
				#G_i_j[1]= G_i_j[1] + [0., 0., -1., 0., 0.]
				#G_i_j[2]= G_i_j[2] + [0., 0., 0., -1., 0.]
				#G_i_j[3]= G_i_j[3] + [0., 0., 0., 0., -1.]
				#h_i_j = h_i_j + [1., 0., 0., 0., 0.]
				G = matrix(G_i_j_k)
				h = matrix(h_i_j_k)
				#G = matrix(G_i_j)
			#	h = matrix([-1 * penalty, 1., 0., 0., 0.])
				#h = matrix(h_i_j)
				dims = {'l':  len(mus) + len(mu_CEXs) * len(mu_Gs), 'q': [1 + len(mus[i])], 's': []}
				sol = solvers.conelp(c, G, h, dims)
				sol['status']
				solution = np.array(sol['x'])
				if solution is not None:
					solution=solution.reshape(len(mus[i]))
					w_delta_mu=np.dot(solution, (1 - safety) * (exp_mu - mus[i]) + safety * (mu_CEXs[j] - mu_Gs[k]))
					w_delta_mus[i][j][k] = w_delta_mu
				else:
					w_delta_mus[i][j][k] = None
				solutions[i][j][k]=solution/np.linalg.norm(solution, ord=2)
			#indices[i].append(np.argmax(w_delta_mus[i][j]))
			#if w_delta_mus[i][j][indices[i][j]] > max_w_delta_mus:
			#	max_w_delta_mus = w_delta_mus[i][j][indices[i][j]]
			if w_delta_mus[i][j][np.argmax(w_delta_mus[i][j])] > max_w_delta_mus:
				max_w_delta_mus = w_delta_mus[i][j][np.argmax(w_delta_mus[i][j])]
				index = [np.argmax(w_delta_mus[i][j]), j, i]
	return index, solutions[index[-1]][index[-2]][index[0]], w_delta_mus[index[-1]][index[-2]][index[0]]

def multi_learn(grids, agent, theta, exp_policy, exp_mu, starts=None, steps=float("inf"), epsilon=1e-4, iteration=20, gamma=0.9, safety = 0.02):
	print "starting multiple goal learning"
	new_theta = theta
	new_policy = exp_policy
	new_mu = optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
	print "first theta is ", new_theta
	print "first feature is ", new_mu
	exp_u_G, p_G, exp_u_B, p_B, P = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = epsilon, gamma=gamma)
	p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))
	print "when feature matched, unsafe rate ", p_B_sum
	while p_B_sum > safety:
		new_mu_B = np.sum(np.reshape(exp_u_B, [grids.y_max * grids.x_max, len(grids.features[-1][-1])]), 0)
		
		print "failure path feature", new_mu_B
		new_mu = (new_mu - 0.5 * new_mu_B)/(1 - 0.5)	
		print "updated feature ", new_mu
		_, new_theta, new_policy, _= expert_train(grids, new_mu, agent, starts = starts, steps=steps, epsilon=epsilon, iteration=iteration, gamma=gamma, start_theta= None, MC = False, safety = None)
		print "new theta ", new_theta
		#new_mu = optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
		print "new feature ", new_mu
		exp_u_G, p_G, exp_u_B, p_B, P = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = epsilon, gamma=gamma)
		p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))
		print "when feature matched, unsafe rate ", p_B_sum
	print "Finally safe"
	print "theta is ", new_theta	
	print "policy is "
	print new_policy 
	return new_policy


def MC_synthesize(grids, expert, agent, starts, steps, epsilon=1e-6, iteration=100, gamma=0.5, start_theta= None, MC = False, unsafe = None, safety = 0.0001, exp_policy = None):
	print "Human demo feature ", expert
	print "AL learnt theta ", start_theta
	flag = None
	itr = 0
	thetas = []
	mu_CEXs = []
	mus = [ 0.0 * expert]
	mus_ = [ 0.0 * expert]
	mu_Bs = []
	policies = []	
	grids.w_features(start_theta)
	start_policy, start_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma, toolbox = False, starts = starts)
	#policies = policies + [start_policy]
	new_policy = start_policy
	#return start_theta, start_policy, start_value, None

	exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = epsilon , gamma=gamma, bounds = np.zeros([len(starts)]), unsafe = unsafe)
	start_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 
	new_mu_B = np.sum(np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]), 0) 
	p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))

	new_mu = start_mu
	#mus_ = mus_ + [new_mu]
	#print "Add uncheck features ", new_mu
	#mus.append(new_mu)
	#expert = np.array(start_mu)
	#print "expert feature changed to ", start_mu

	new_theta = np.array(start_theta)
	grids.w_features(new_theta)
	#thetas.append(new_theta)
	print "Initial unsafe path rate ", p_B_sum

	print "model output finished for initial policy"
	if p_B_sum <= safety and p_B_sum is not None:
		return grids, start_theta, start_policy, p_B_sum

	if p_B_sum > safety:
		print "Keep generating counterexamples until find a safe candidate" 
		if new_mu_B is not None:
			mu_Bs = mu_Bs + [new_mu_B]
		else:
			print "Failed to find counterexample"
			return None

	#exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, exp_policy, epochs= 5000, epsilon = epsilon , gamma=gamma, bounds = np.zeros([len(starts)]), unsafe = unsafe)
	#new_mu_B = np.sum(np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]), 0) 
	#p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))
	if p_B_sum <= safety:
		print "Provided policy is safe"
		safe_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 
		mus.append(safe_mu)
		mus_.append(safe_mu)
		flag = {'weight': None, 'policy': exp_policy, 'value': None, 'unsafe': safety, 'feature': safe_mu}

	INF = 0.0
	SUP = 1.0
	K = 0.5
	mu = [[1.0 - K,  K],[mu_Bs, [expert]]]

	new_index, new_theta, w_delta_mu = expert_update_theta_v3(grids, mu, agent, steps, policies, [mus, mus_], gamma, epsilon)
	grids.w_features(new_theta)
	print "Weight learnt from 1st combined feature ", new_theta
	
	new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)
	exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = epsilon , gamma=gamma, bounds = np.zeros([len(starts)]), unsafe = unsafe)
	new_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 
	new_mu_B = np.sum(np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]), 0) 
	p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))
	print "Policy unsafe rate ", p_B_sum

	while itr >= 0 and itr <= iteration:
		print ">>>>>>>>> ", itr, "th iteration\n", "candidate theta: ", new_theta, "\nunsafe probability:", p_B_sum, "\nfeature ", new_mu, " = ", 1.0 - K, "*safe + ", K, "*expert, inf is " + str(INF) + "\n" 
		file = open('log', 'a')
		file.write(">>>>>>>>> " + str(itr) + "th iteration, candidate theta: "+ str(new_theta) + "; unsafe probability: " + str(p_B_sum) + "; feature " + str(new_mu) + " = " + str(1.0 - K) + "*safe + " + str(K) + "*expert, inf is " + str(INF) + "\n") 
		file.close()
		itr = itr + 1
		
		if itr >= iteration:
			break
		
		if abs(INF - SUP) < 1.0:
			if abs(INF - K) < epsilon or abs(SUP - K) < epsilon:
				if len(mus) >= 2:
					if np.linalg.norm(mus[-1] - mus[-2], ord = 2) < epsilon:
						print ">>>>>>>>>>>>>>>Convergeed<<<<<<<<<<<<<<<<Can't find more policy>>>>"
						break
				if len(mu_Bs) >= 2 and p_B_sum > safety:
					if  np.linalg.norm(mu_Bs[-1] - mu_Bs[-2], ord = 2) < epsilon:
						print ">>>>>>>>>>>>>>>Convergeed<<<<<<<<<<<<<<<<Can't find more counterexample>>>"
						break
			#print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
			#print "Expert can get value ", np.dot(theta, expertw)
			#flag = [new_theta, new_policy, new_value, new_mu]
			#return grids, flag[0], flag[1], flag[2]
		new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)

		exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = epsilon , gamma=gamma, bounds = np.zeros([len(starts)]), unsafe = unsafe)
		start_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 
		new_mu_B = np.sum(np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]), 0) 
		p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))

		print "Corresponding feature ", new_mu
		mus_ = mus_ + [new_mu]
		print "Add uncheck features ", new_mu

		if p_B_sum is not None and p_B_sum > safety:
			print "Unsafe, learning from counterexample"
			#while p_B_sum > safety:
			#new_mu_B = np.sum(np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]), 0) 
			#new_mu_B =  counterexample(grids, grids.features, gamma, safety, epsilon, steps)
			#if new_mu_B is not None:
			#	mu_Bs = mu_Bs + [new_mu_B]
			#	print "Add counterexample features ", new_mu_B	
			#if new_mu_B is None:
			#	print "Can't find more different counterexample"
				#break
				#return grids, flag['weight'], flag['policy'], flag['value']

			print "Learning under same k"
			#new_mu_B =  counterexample(grids, grids.features, gamma, safety, epsilon, steps)
			ignore = False
			if new_mu_B is None:
				#return grids, flag['weight'], flag['policy'], flag['value']
				print "Somehow can't find more different counterexample"
			else:
				mu_Bs = mu_Bs + [new_mu_B]	
			K = (K + INF)/2.0
			mu = [[1.0 - K,  K],[mu_Bs, [expert]]]
			new_index, new_theta, w_delta_mu = expert_update_theta_v3(grids, mu, agent, steps, policies, [mus, mus_], gamma, epsilon)
			grids.w_features(new_theta)
			print "Weight learnt from combined feature ", new_theta


		elif p_B_sum is not None and p_B_sum <= safety:	
			print "Safe, learning from expert"
			mus = mus + [new_mu]
			thetas = thetas + [new_theta]
			policies = policies + [new_policy]
			if flag is not None and np.linalg.norm(expert - new_mu, ord=2)  < np.linalg.norm(expert - flag['feature'], ord=2):
			#if flag is not None and np.dot(new_theta, expert) > np.dot(flag['weight'], expert):
				flag = {'weight': new_theta, 'policy': new_policy, 'value': new_value, 'unsafe': p_B_sum, 'feature': new_mu}
				print "New best candidate"
				print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
				print "Expert can get value ", np.dot(new_theta, expert)
				K = (SUP + K)/2
			elif flag is None:
				flag = {'weight': new_theta, 'policy': new_policy, 'value': new_value, 'unsafe': p_B_sum, 'feature': new_mu}
				print "1st best candidate"
				print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
				print "Expert can get value ", np.dot(new_theta, expert)
				K = (SUP + K)/2

			else:
				print "Not the best"
				print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
				print "Expert can get value ", np.dot(new_theta, expert)
				K = (SUP + K)/2

			print "Add new candidate policy expected feature", new_mu
			
			mu = [[1.0 - K,  K],[mu_Bs, [expert]]]
			#grids, new_theta, new_policy, new_value = expert_train_v1(grids, mu, agent, starts, steps, epsilon=epsilon, iteration=30, gamma=gamma, start_theta= new_theta, MC = False, safety = None)
			new_index, new_theta, w_delta_mu = expert_update_theta_v3(grids, mu, agent, steps, policies, [mus, mus_], gamma, epsilon)
			grids.w_features(new_theta)
			print "Weight learnt from combined feature ", new_theta
			new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)
			policies = policies + [new_policy]

			exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, grids.x_max*grids.y_max, new_policy, epochs= 5000, epsilon = 1e-3, gamma=gamma)
			p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))
			print "Policy unsafe rate ", p_B_sum
			if p_B_sum <= safety:
				INF = K
				K = SUP
				
	

		print "Add uncheck features ", new_mu
	'''
	index, _, w_delta_mu = expert_update_theta(grids, expert, agent, steps, policies, mus, gamma=gamma, epsilon = epsilon)
	print "Iteration ended, best safe theta ", thetas[index]
	print "It's unsafe probability is satisfied"
	print "Distance to expert feature ", w_delta_mu

	return grids, thetas[index], policies[index], w_delta_mu
	'''
	print "Iteration ended, best safe theta ", flag['weight']
	print "It's unsafe probability is ", flag['unsafe']
	print "Distance to expert feature ", np.linalg.norm(expert - flag['feature'], ord= 2)
	return grids, flag['weight'], flag['policy'], flag['unsafe']


def expert_synthesize(grids, expert, agent, starts, steps, epsilon=1e-6, iteration=100, gamma=0.5, start_theta= None, MC = False, unsafe = None, safety = 0.0001, exp_policy = None):
	print "Human demo feature ", expert
	print "AL learnt theta ", start_theta
	flag = None
	itr = 0
	thetas = []
	mu_CEXs = []
	mus = [ 0.0 * expert]
	mus_ = [ 0.0 * expert]
	mu_Bs = []
	policies = []	
	grids.w_features(start_theta)
	start_policy, start_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma, toolbox = False, starts = starts)
	#policies = policies + [start_policy]
	new_policy = start_policy
	#return start_theta, start_policy, start_value, None
	if MC is False:
		start_mu, MU = optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
	else:
		exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = epsilon , gamma=gamma, bounds = np.zeros([len(starts)]), unsafe = unsafe)

		start_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 
		
	new_mu = start_mu
	#mus_ = mus_ + [new_mu]
	#print "Add uncheck features ", new_mu
	#mus.append(new_mu)
	#expert = np.array(start_mu)
	#print "expert feature changed to ", start_mu

	new_theta = np.array(start_theta)
	grids.w_features(new_theta)
	#thetas.append(new_theta)
	p_B_sum = output_model(grids, starts, start_policy, steps, unsafe, safety)
	#exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, grids.x_max*grids.y_max, start_policy, epochs= 5000, epsilon = 1e-3, gamma=gamma)
	#p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))
	print "Initial unsafe path rate ", p_B_sum

	print "model output finished for initial policy"
	if p_B_sum <= safety and p_B_sum is not None:
		return grids, start_theta, start_policy, p_B_sum

	if p_B_sum > safety:
		print "Keep generating counterexamples until find a safe candidate" 
		new_mu_B =  counterexample(grids, grids.features, gamma, safety, epsilon, steps)
		#new_mu_B = np.sum(np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]), 0) 
		if new_mu_B is not None:
			mu_Bs = mu_Bs + [new_mu_B]
		else:
			print "Failed to find counterexample"
			return None

	if exp_policy is not None:
		p_B_sum = output_model(grids, starts, exp_policy, steps, unsafe, safety)
		if p_B_sum <= safety:
			print "Provided policy is safe"
			safe_mu, MU = optimal_feature(grids, starts, steps, exp_policy, epsilon = epsilon, gamma=gamma)
			mus.append(safe_mu)
			mus_.append(safe_mu)
			flag = {'weight': None, 'policy': exp_policy, 'value': None, 'unsafe': safety, 'feature': safe_mu}

	INF = 0.0
	SUP = 1.0
	K = 0.5
	mu = [[1.0 - K,  K],[mu_Bs, [expert]]]

	new_index, new_theta, w_delta_mu = expert_update_theta_v3(grids, mu, agent, steps, policies, [mus, mus_], gamma, epsilon)
	grids.w_features(new_theta)
	print "Weight learnt from 1st combined feature ", new_theta
	
	new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)
	p_B_sum = output_model(grids, starts, new_policy, steps, unsafe, safety)
	print "Policy unsafe rate ", p_B_sum

	while itr >= 0 and itr <= iteration:
		print ">>>>>>>>> ", itr, "th iteration\n", "candidate theta: ", new_theta, "\nunsafe probability:", p_B_sum, "\nfeature ", new_mu, " = ", 1.0 - K, "*safe + ", K, "*expert, inf is " + str(INF) + "\n" 
		file = open('log', 'a')
		file.write(">>>>>>>>> " + str(itr) + "th iteration, candidate theta: "+ str(new_theta) + "; unsafe probability: " + str(p_B_sum) + "; feature " + str(new_mu) + " = " + str(1.0 - K) + "*safe + " + str(K) + "*expert, inf is " + str(INF) + "\n") 
		file.close()
		itr = itr + 1
		
		if itr >= iteration:
			break
		
		if abs(INF - SUP) < 1.0:
			if abs(INF - K) < epsilon or abs(SUP - K) < epsilon:
				if len(mus) >= 2:
					if np.linalg.norm(mus[-1] - mus[-2], ord = 2) < epsilon:
						print ">>>>>>>>>>>>>>>Convergeed<<<<<<<<<<<<<<<<Can't find more policy>>>>"
						break
				if len(mu_Bs) >= 2 and p_B_sum > safety:
					if  np.linalg.norm(mu_Bs[-1] - mu_Bs[-2], ord = 2) < epsilon:
						print ">>>>>>>>>>>>>>>Convergeed<<<<<<<<<<<<<<<<Can't find more counterexample>>>"
						break
			#print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
			#print "Expert can get value ", np.dot(theta, expertw)
			#flag = [new_theta, new_policy, new_value, new_mu]
			#return grids, flag[0], flag[1], flag[2]
		if MC is False:
			new_mu, MU = optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
		else:
			exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = epsilon, gamma=gamma, bounds = np.zeros([len(starts)]), unsafe = unsafe)
			new_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 
		print "Corresponding feature ", new_mu
		#if len(mus) > 1:
		#	mus_ = mus_ + [new_mu]
		print "Add uncheck features ", new_mu

		if p_B_sum is not None and p_B_sum > safety:
			print "Unsafe, learning from counterexample"
			#while p_B_sum > safety:
			#new_mu_B = np.sum(np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]), 0) 
			#new_mu_B =  counterexample(grids, grids.features, gamma, safety, epsilon, steps)
			#if new_mu_B is not None:
			#	mu_Bs = mu_Bs + [new_mu_B]
			#	print "Add counterexample features ", new_mu_B	
			#if new_mu_B is None:
			#	print "Can't find more different counterexample"
				#break
				#return grids, flag['weight'], flag['policy'], flag['value']
			if len(mus) > 1 and np.linalg.norm(new_mu - flag['feature'], ord = 2) < 0:
				mus_ = mus_ + [new_mu]
			print "Add unsafe policy candidate"
			print "Learning under same k"
			new_mu_B =  counterexample(grids, grids.features, gamma, safety, epsilon, steps)
			ignore = False
			if new_mu_B is None:
				#return grids, flag['weight'], flag['policy'], flag['value']
				print "Somehow can't find more different counterexample"
			else:
				mu_Bs = mu_Bs + [new_mu_B]	
			#K = (K + INF)/2.0
			K = K**2
			mu = [[1.0 - K,  K],[mu_Bs, [expert]]]
			new_index, new_theta, w_delta_mu = expert_update_theta_v3(grids, mu, agent, steps, policies, [mus, mus_], gamma, epsilon)
			grids.w_features(new_theta)
			print "Weight learnt from combined feature ", new_theta
			new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)
			'''
			if MC is False:
				new_mu, MU = optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
			else:
				exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = epsilon, gamma=gamma, bounds = np.zeros([len(starts)]), unsafe = unsafe)
				new_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 
			print "Corresponding feature ", new_mu
			mus_ = mus_ + [new_mu]
			print "Add uncheck features ", new_mu
			'''
			p_B_sum = output_model(grids, starts, new_policy, steps, unsafe, safety)
			print "Policy unsafe rate ", p_B_sum

		elif p_B_sum is not None and p_B_sum <= safety:	
			mus_ = mus_ + [new_mu]
			print "Safe, learning from expert"
			mus = mus + [new_mu]
			thetas = thetas + [new_theta]
			policies = policies + [new_policy]
			if flag is not None and np.linalg.norm(expert - new_mu, ord=2)  < np.linalg.norm(expert - flag['feature'], ord=2):
			#if flag is not None and np.dot(new_theta, expert) > np.dot(flag['weight'], expert):
				flag = {'weight': new_theta, 'policy': new_policy, 'value': new_value, 'unsafe': p_B_sum, 'feature': new_mu}
				print "New best candidate"
				print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
				print "Expert can get value ", np.dot(new_theta, expert)
				#INF = (K + INF)/2
				#K = (SUP + K)/2
				K = K + (INF - K) * K
			elif flag is None:
				flag = {'weight': new_theta, 'policy': new_policy, 'value': new_value, 'unsafe': p_B_sum, 'feature': new_mu}
				print "1st best candidate"
				print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
				print "Expert can get value ", np.dot(new_theta, expert)
				#INF = (K + INF)/2
				#K = (SUP + K)/2
				K = K + (INF - K) * K

			else:
				print "Not the best"
				print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
				print "Expert can get value ", np.dot(new_theta, expert)
				#INF = (K + INF)/2
				#K = (SUP + K)/2
				K = K + (INF - K) * K

			print "Add new candidate policy expected feature", new_mu
			
			mu = [[1.0 - K,  K],[mu_Bs, [expert]]]
			#grids, new_theta, new_policy, new_value = expert_train_v1(grids, mu, agent, starts, steps, epsilon=epsilon, iteration=30, gamma=gamma, start_theta= new_theta, MC = False, safety = None)
			new_index, new_theta, w_delta_mu = expert_update_theta_v3(grids, mu, agent, steps, policies, [mus, mus_], gamma, epsilon)
			grids.w_features(new_theta)
			print "Weight learnt from combined feature ", new_theta
			new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)
			#policies = policies + [new_policy]

			p_B_sum = output_model(grids, starts, new_policy, steps, unsafe, safety)
			#exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, grids.x_max*grids.y_max, new_policy, epochs= 5000, epsilon = 1e-3, gamma=gamma)
			#p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))
			print "Policy unsafe rate ", p_B_sum
			#if p_B_sum <= safety:
			#	K = SUP
				
	

		print "Add uncheck features ", new_mu
	'''
	index, _, w_delta_mu = expert_update_theta(grids, expert, agent, steps, policies, mus, gamma=gamma, epsilon = epsilon)
	print "Iteration ended, best safe theta ", thetas[index]
	print "It's unsafe probability is satisfied"
	print "Distance to expert feature ", w_delta_mu

	return grids, thetas[index], policies[index], w_delta_mu
	'''
	print "Iteration ended, best safe theta ", flag['weight']
	print "It's unsafe probability is ", flag['unsafe']
	print "Distance to expert feature ", np.linalg.norm(expert - flag['feature'], ord= 2)
	return grids, flag['weight'], flag['policy'], flag['unsafe']


def expert_synthesize1(grids, expert, agent, starts, steps, epsilon=1e-6, iteration=100, gamma=0.5, start_theta= None, MC = False, unsafe = None, safety = 0.0001, exp_policy = None):
	print "Human demo feature ", expert
	print "AL learnt theta ", start_theta
	flag = None
	itr = 0
	thetas = []
	mu_CEXs = []
	mus = [ 0.0 * expert]
	mus_ = [ 0.0 * expert]
	#mus_ = []
	mu_Bs = []
	policies = []	
	grids.w_features(start_theta)
	start_policy, start_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma, toolbox = False, starts = starts)
	#policies = policies + [start_policy]
	new_policy = start_policy
	#return start_theta, start_policy, start_value, None
	if MC is False:
		start_mu, MU = optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
	else:
		exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = epsilon , gamma=gamma, bounds = np.zeros([len(starts)]), unsafe = unsafe)

		start_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 
		
	new_mu = start_mu
	#mus_ = mus_ + [new_mu]
	#print "Add uncheck features ", new_mu
	#mus.append(new_mu)
	#expert = np.array(start_mu)
	#print "expert feature changed to ", start_mu

	new_theta = np.array(start_theta)
	grids.w_features(new_theta)
	#thetas.append(new_theta)
	p_B_sum = output_model(grids, starts, start_policy, steps, unsafe, safety)
	#exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, grids.x_max*grids.y_max, start_policy, epochs= 5000, epsilon = 1e-3, gamma=gamma)
	#p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))
	print "Initial unsafe path rate ", p_B_sum

	print "model output finished for initial policy"
	if p_B_sum <= safety and p_B_sum is not None:
		return grids, start_theta, start_policy, p_B_sum

	if p_B_sum > safety:
		print "Keep generating counterexamples until find a safe candidate" 
		new_mu_B =  counterexample(grids, grids.features, gamma, safety, epsilon, steps)
		#new_mu_B = np.sum(np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]), 0) 
		if new_mu_B is not None:
			mu_Bs = mu_Bs + [new_mu_B]
		else:
			print "Failed to find counterexample"
			return None

	if exp_policy is not None:
		p_B_sum = output_model(grids, starts, exp_policy, steps, unsafe, safety)
		if p_B_sum <= safety:
			print "Provided policy is safe"
			safe_mu, MU = optimal_feature(grids, starts, steps, exp_policy, epsilon = epsilon, gamma=gamma)
			mus.append(safe_mu)
			mus_.append(safe_mu)
			flag = {'weight': None, 'policy': exp_policy, 'value': None, 'unsafe': safety, 'feature': safe_mu}

	INF = 0.0
	SUP = 1.0
	K = 0.5
	mu = [[1.0 - K,  K],[mu_Bs, [expert]]]

	new_index, new_theta, w_delta_mu = expert_update_theta_v3(grids, mu, agent, steps, policies, [mus, mus_], gamma, epsilon)
	grids.w_features(new_theta)
	print "Weight learnt from 1st combined feature ", new_theta
	
	new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)
	p_B_sum = output_model(grids, starts, new_policy, steps, unsafe, safety)
	print "Policy unsafe rate ", p_B_sum

	while itr >= 0 and itr <= iteration:
		print ">>>>>>>>> ", itr, "th iteration\n", "candidate theta: ", new_theta, "\nunsafe probability:", p_B_sum, "\nfeature ", new_mu, " = ", 1.0 - K, "*safe + ", K, "*expert, inf is " + str(INF) + "\n" 
		file = open('log', 'a')
		file.write(">>>>>>>>> " + str(itr) + "th iteration, candidate theta: "+ str(new_theta) + "; unsafe probability: " + str(p_B_sum) + "; feature " + str(new_mu) + " = " + str(1.0 - K) + "*safe + " + str(K) + "*expert, inf is " + str(INF) + "\n") 
		file.close()
		itr = itr + 1
		
		if itr >= iteration:
			break
		
		if abs(INF - SUP) < 1.0:
			if abs(INF - K) < epsilon or abs(SUP - K) < epsilon:
				if len(mus) >= 2:
					if np.linalg.norm(mus[-1] - mus[-2], ord = 2) < epsilon:
						print ">>>>>>>>>>>>>>>Convergeed<<<<<<<<<<<<<<<<Can't find more policy>>>>"
						break
				if len(mu_Bs) >= 2 and p_B_sum > safety:
					if  np.linalg.norm(mu_Bs[-1] - mu_Bs[-2], ord = 2) < epsilon:
						print ">>>>>>>>>>>>>>>Convergeed<<<<<<<<<<<<<<<<Can't find more counterexample>>>"
						break
			#print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
			#print "Expert can get value ", np.dot(theta, expertw)
			#flag = [new_theta, new_policy, new_value, new_mu]
			#return grids, flag[0], flag[1], flag[2]
		if MC is False:
			new_mu, MU = optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
		else:
			exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = epsilon, gamma=gamma, bounds = np.zeros([len(starts)]), unsafe = unsafe)
			new_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 
		print "Corresponding feature ", new_mu
		mus_ = mus_ + [new_mu]
		print "Add uncheck features ", new_mu

		if p_B_sum is not None and p_B_sum > safety:
			print "Unsafe, learning from counterexample"
			#while p_B_sum > safety:
			#new_mu_B = np.sum(np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]), 0) 
			#new_mu_B =  counterexample(grids, grids.features, gamma, safety, epsilon, steps)
			#if new_mu_B is not None:
			#	mu_Bs = mu_Bs + [new_mu_B]
			#	print "Add counterexample features ", new_mu_B	
			#if new_mu_B is None:
			#	print "Can't find more different counterexample"
				#break
				#return grids, flag['weight'], flag['policy'], flag['value']

			print "Learning under same k"
			new_mu_B =  counterexample(grids, grids.features, gamma, safety, epsilon, steps)
			ignore = False
			if new_mu_B is None:
				#return grids, flag['weight'], flag['policy'], flag['value']
				print "Somehow can't find more different counterexample"
			else:
				mu_Bs = mu_Bs + [new_mu_B]	
			K = (K + INF)/2.0
			mu = [[1.0 - K,  K],[mu_Bs, [expert]]]
			new_index, new_theta, w_delta_mu = expert_update_theta_v3(grids, mu, agent, steps, policies, [mus, mus_], gamma, epsilon)
			grids.w_features(new_theta)
			print "Weight learnt from combined feature ", new_theta
			new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)
			if MC is False:
				new_mu, MU = optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
			else:
				exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = epsilon, gamma=gamma, bounds = np.zeros([len(starts)]), unsafe = unsafe)
				new_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 
			print "Corresponding feature ", new_mu
			mus_ = mus_ + [new_mu]
			print "Add uncheck features ", new_mu

			p_B_sum = output_model(grids, starts, new_policy, steps, unsafe, safety)
			print "Policy unsafe rate ", p_B_sum

		elif p_B_sum is not None and p_B_sum <= safety:	
			print "Safe, learning from expert"
			mus = mus + [new_mu]
			thetas = thetas + [new_theta]
			policies = policies + [new_policy]
			if flag is not None and np.linalg.norm(expert - new_mu, ord=2)  < np.linalg.norm(expert - flag['feature'], ord=2):
			#if flag is not None and np.dot(new_theta, expert) > np.dot(flag['weight'], expert):
				flag = {'weight': new_theta, 'policy': new_policy, 'value': new_value, 'unsafe': p_B_sum, 'feature': new_mu}
				print "New best candidate"
				print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
				print "Expert can get value ", np.dot(new_theta, expert)
				K = (SUP + K)/2
			elif flag is None:
				flag = {'weight': new_theta, 'policy': new_policy, 'value': new_value, 'unsafe': p_B_sum, 'feature': new_mu}
				print "1st best candidate"
				print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
				print "Expert can get value ", np.dot(new_theta, expert)
				K = (SUP + K)/2

			else:
				print "Not the best"
				print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
				print "Expert can get value ", np.dot(new_theta, expert)
				K = (SUP + K)/2

			print "Add new candidate policy expected feature", new_mu
		
			if len(mus) >= 2 and np.linalg.norm(mus[-1] - mus[-2]) <= epsilon:
				INF = K
			
			mu = [[1.0 - K,  K],[mu_Bs, [expert]]]
			#grids, new_theta, new_policy, new_value = expert_train_v1(grids, mu, agent, starts, steps, epsilon=epsilon, iteration=30, gamma=gamma, start_theta= new_theta, MC = False, safety = None)
			new_index, new_theta, w_delta_mu = expert_update_theta_v3(grids, mu, agent, steps, policies, [mus, mus_], gamma, epsilon)
			grids.w_features(new_theta)
			print "Weight learnt from combined feature ", new_theta
			new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)
			#policies = policies + [new_policy]

			p_B_sum = output_model(grids, starts, new_policy, steps, unsafe, safety)
			#exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, grids.x_max*grids.y_max, new_policy, epochs= 5000, epsilon = 1e-3, gamma=gamma)
			#p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))
			print "Policy unsafe rate ", p_B_sum
				
	

		print "Add uncheck features ", new_mu
	'''
	index, _, w_delta_mu = expert_update_theta(grids, expert, agent, steps, policies, mus, gamma=gamma, epsilon = epsilon)
	print "Iteration ended, best safe theta ", thetas[index]
	print "It's unsafe probability is satisfied"
	print "Distance to expert feature ", w_delta_mu

	return grids, thetas[index], policies[index], w_delta_mu
	'''
	print "Iteration ended, best safe theta ", flag['weight']
	print "It's unsafe probability is ", flag['unsafe']
	print "Distance to expert feature ", np.linalg.norm(expert - flag['feature'], ord= 2)
	return grids, flag['weight'], flag['policy'], flag['unsafe']
				



def expert_synthesize2(grids, expert, agent, starts, steps, epsilon=1e-6, iteration=100, gamma=0.5, start_theta= None, MC = False, unsafe = None, safety = 0.0001, exp_policy = None):
	print "Human demo feature ", expert
	print "AL learnt theta ", start_theta
	flag = None
	itr = 0
	thetas = []
	mu_CEXs = []
	mus = []
	mus_ = []
	mu_Bs = []
	policies = []	
	grids.w_features(start_theta)
	start_policy, start_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma, toolbox = False, starts = starts)
	#policies = policies + [start_policy]
	new_policy = start_policy
	#return start_theta, start_policy, start_value, None
	if MC is False:
		start_mu, MU = optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
	else:
		exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = epsilon , gamma=gamma, bounds = np.zeros([len(starts)]), unsafe = unsafe)

		start_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 
		
	new_mu = start_mu
	mus_ = mus_ + [new_mu]
	print "Add uncheck features ", new_mu
	#mus.append(new_mu)
	#expert = np.array(start_mu)
	#print "expert feature changed to ", start_mu

	new_theta = np.array(start_theta)
	grids.w_features(new_theta)
	#thetas.append(new_theta)
	p_B_sum = output_model(grids, starts, start_policy, steps, unsafe, safety)
	#exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, grids.x_max*grids.y_max, start_policy, epochs= 5000, epsilon = 1e-3, gamma=gamma)
	#p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))
	print "Initial unsafe path rate ", p_B_sum

	print "model output finished for initial policy"
	if p_B_sum <= safety and p_B_sum is not None:
		return grids, start_theta, start_policy, start_value

	while p_B_sum > safety:
		print "Keep generating counterexamples until find a safe candidate" 
		new_mu_B =  counterexample(grids, grids.features, gamma, safety, epsilon, steps)
		#new_mu_B = np.sum(np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]), 0) 
		if new_mu_B is not None:
			if len(mu_Bs) > 2:
				if np.linalg.norm(new_mu_B - mu_Bs[-1], ord=2) < epsilon:
					print "Can't find more diffferent counterexample"
					print "Failed to find safe policy"
					break
			mu_Bs = mu_Bs + [new_mu_B]
			print "Add counterexample features ", new_mu_B	
		elif len(mu_Bs) == 0:
			print "Failed to find counterexample"
			break

		new_index, new_theta, w_delta_mu = expert_update_theta(grids, np.zeros(len(grids.features[-1][-1])), agent, steps, policies, mu_Bs, gamma, epsilon)
		#thetas.append(new_theta)
		if len(thetas) > 2:
			if np.linalg.norm(thetas[-1] - thetas[-2], ord = 2) < epsilon:
				print "Can't find more diffferent counterexample"
				print "Failed to find safe policy"
				break
		grids.w_features(new_theta)
		print "Weight learnt from counterexamples ", new_theta

		new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)
		if MC is False:
			new_mu, MU = optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
		else:
			exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = epsilon, gamma=gamma, bounds = np.zeros([len(starts)]), unsafe = unsafe)
			new_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 
		print "Corresponding feature ", new_mu
		mus_ = mus_ + [new_mu]
		print "Add uncheck features ", new_mu

		p_B_sum = output_model(grids, starts, new_policy, steps, unsafe, safety)
		#exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, grids.x_max*grids.y_max, new_policy, epochs= 5000, epsilon = 1e-3, gamma=gamma)
		#p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))
		print "Policy unsafe rate ", p_B_sum

		
	if p_B_sum > safety and exp_policy is not None:
		print "Try a again: Test hand made policy"
		new_theta = -1.0 * np.ones([len(grids.features[-1][-1])]).astype(float)
		new_theta = new_theta/np.linalg.norm(new_theta, ord= 2)
		new_value = None
		new_policy = np.array(exp_policy)
		p_B_sum = output_model(grids, starts, new_policy, steps, unsafe, safety)
		print "Policy unsafe rate ", p_B_sum
	if p_B_sum > safety:
		print "No hope"
		return None

     	print "Found 1st safe policy towards safety ", new_theta	
	mus = mus + [new_mu]
	thetas = thetas + [new_theta]
	policies = policies + [new_policy]
	flag = {'weight': new_theta, 'policy': new_policy, 'value': new_value, 'unsafe': p_B_sum, 'feature': new_mu}


	K_EXP = 1.0
	K_CEX = 0.0
	K = 1.0
	mu = [[1.0 - K,  K],[mu_Bs, [expert]]]

	if len(mu_Bs) == 0:
		print "No counterexample found"
		return None
		
	new_index, new_theta, w_delta_mu = expert_update_theta(grids, expert, agent, steps, policies, mus_ + mus, gamma, epsilon)
	grids.w_features(new_theta)
	print "Weight learnt from 1st combined feature ", new_theta
	
	new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)
	p_B_sum = output_model(grids, starts, new_policy, steps, unsafe, safety)
	print "Policy unsafe rate ", p_B_sum
	while True:
		if MC is False:
			new_mu, MU = optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
		else:
			exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = epsilon, gamma=gamma, bounds = np.zeros([len(starts)]), unsafe = unsafe)
			new_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 
		print "Corresponding feature ", new_mu
		print "Add uncheck features ", new_mu
		mus_ = mus_ + [new_mu]
		#exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, grids.x_max*grids.y_max, new_policy, epochs= 5000, epsilon = 1e-3, gamma=gamma)
		#p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))

		if p_B_sum <= safety:
			itr  = 0
			ignore = False
			for e in mus:
				if np.linalg.norm(e - new_mu, ord = 2) < epsilon:
					ignore = True
					break
			if ignore is False:
				print "Same k, found safe policy"
				mus = mus + [new_mu]
				thetas = thetas + [new_theta]
				policies = policies + [new_policy]
				#if flag is not None and np.linalg.norm(expert - new_mu, ord=2)  < np.linalg.norm(expert - flag['feature'], ord=2):
				if flag is not None and np.dot(new_theta, expert) > np.dot(flag['weight'], expert):
					flag = {'weight': new_theta, 'policy': new_policy, 'value': new_value, 'unsafe': p_B_sum, 'feature': new_mu}
					print "New best candidate"
					print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
					print "Expert can get value ", np.dot(new_theta, expert)
			else:
				print "Can't find more different safe policy. That's it."
				mus = mus + [new_mu]
				thetas = thetas + [new_theta]
				policies = policies + [new_policy]
				break
		elif p_B_sum > safety:
			new_mu_B =  counterexample(grids, grids.features, gamma, safety, epsilon, steps)
			itr  = 1
			if new_mu_B is None:
				#return grids, flag['weight'], flag['policy'], flag['value']
				print "Can't find counterexample"
				break
			ignore = False
			for e in mu_Bs:
				if np.linalg.norm(new_mu_B - e, ord =2) < epsilon:
					ignore = True
					break
			if ignore is False:
				print "Found different counterexample"
				mu_Bs = mu_Bs + [new_mu_B]	
				break
			else:
				print "Can't find more different counterexample. Begin iteration"
				mu_Bs = mu_Bs + [new_mu_B]	
				break
			break
		print "Learning from pure expert"
		mu = [[1.0 - K,  K],[mu_Bs, [expert]]]
		new_index, new_theta, w_delta_mu = expert_update_theta_v3(grids, mu, agent, steps, policies, [mus, mus_], gamma, epsilon)
		grids.w_features(new_theta)
		print "Weight learnt from pure expert ", new_theta
		new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)
		p_B_sum = output_model(grids, starts, new_policy, steps, unsafe, safety)
		print "Policy unsafe rate ", p_B_sum

	while itr > 0 and itr <= iteration:
		print ">>>>>>>>> ", itr, "th iteration\n", "candidate theta: ", new_theta, "\nunsafe probability:", p_B_sum, "\nfeature ", new_mu, " = ", 1.0 - K, "*safe + ", K, "*expert\n" 
		file = open('log', 'a')
		file.write(">>>>>>>>> " + str(itr) + "th iteration, candidate theta: "+ str(new_theta) + "; unsafe probability: " + str(p_B_sum) + "; feature " + str(new_mu) + " = " + str(1.0 - K) + "*safe + " + str(K) + "*expert\n") 
		file.close()
		itr = itr + 1
		
		if itr >= iteration:
			break
		
		if abs(K_CEX - K_EXP) < 1.0:
			if abs(K_CEX - K) < epsilon or abs(K_EXP - K) < epsilon:
				print ">>>>>>>>>>>>>>>Convergeed<<<<<<<<<<<<<<<<"
				break
				if len(mus) >= 2:
					if np.linalg.norm(mus[-1] - mus[-2], ord = 2) < epsilon:
						print ">>>>>>>>>>>>>>>Convergeed<<<<<<<<<<<<<<<<"
						break
				if len(mu_Bs) >= 2:
					if  np.linalg.norm(mu_Bs[-1] - mu_Bs[-2], ord = 2) < epsilon:
						print ">>>>>>>>>>>>>>>Convergeed<<<<<<<<<<<<<<<<"
						break
			#print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
			#print "Expert can get value ", np.dot(theta, expertw)
			#flag = [new_theta, new_policy, new_value, new_mu]
			#return grids, flag[0], flag[1], flag[2]
		if MC is False:
			new_mu, MU = optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
		else:
			exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = epsilon, gamma=gamma, bounds = np.zeros([len(starts)]), unsafe = unsafe)
			new_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 
		print "Corresponding feature ", new_mu
		mus_ = mus_ + [new_mu]
		print "Add uncheck features ", new_mu

		if p_B_sum is not None and p_B_sum > safety:
			print "Unsafe, learning from counterexample"
			#while p_B_sum > safety:
			#new_mu_B = np.sum(np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]), 0) 
			#new_mu_B =  counterexample(grids, grids.features, gamma, safety, epsilon, steps)
			#if new_mu_B is not None:
			#	mu_Bs = mu_Bs + [new_mu_B]
			#	print "Add counterexample features ", new_mu_B	
			#if new_mu_B is None:
			#	print "Can't find more different counterexample"
				#break
				#return grids, flag['weight'], flag['policy'], flag['value']

			while p_B_sum > safety:
				print "Learning under same k"
				new_mu_B =  counterexample(grids, grids.features, gamma, safety, epsilon, steps)
				if new_mu_B is None:
					#return grids, flag['weight'], flag['policy'], flag['value']
					print "Somehow can't find more different counterexample"
					break
				ignore = False
				for e in mu_Bs:
					if np.linalg.norm(new_mu_B - mu_Bs[-1], ord =2) < epsilon:
						print "Can't find more different counterexample"
						ignore = True
						break
				if ignore is False:
					print "Same k, found different counterexample"
					mu_Bs = mu_Bs + [new_mu_B]	
					break
				else:
					mu_Bs = mu_Bs + [new_mu_B]	
					break
				mu = [[1.0 - K,  K],[mu_Bs, [expert]]]
				new_index, new_theta, w_delta_mu = expert_update_theta_v3(grids, mu, agent, steps, policies, [mus, mus_], gamma, epsilon)
				grids.w_features(new_theta)
				print "Weight learnt from combined feature ", new_theta
				new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)
				if MC is False:
					new_mu, MU = optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
				else:
					exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = epsilon, gamma=gamma, bounds = np.zeros([len(starts)]), unsafe = unsafe)
					new_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 
				print "Corresponding feature ", new_mu
				mus_ = mus_ + [new_mu]
				print "Add uncheck features ", new_mu

				p_B_sum = output_model(grids, starts, new_policy, steps, unsafe, safety)
				print "Policy unsafe rate ", p_B_sum
			if p_B_sum > safety:
				#KK = k
				#k = (K + KK)/2			
				#K_EXP = K
				K = (K + K_CEX)/2.0
			mu = [[1.0 - K,  K],[mu_Bs, [expert]]]
			new_index, new_theta, w_delta_mu = expert_update_theta_v3(grids, mu, agent, steps, policies, [mus, mus_], gamma, epsilon)
			grids.w_features(new_theta)
			print "Weight learnt from combined feature ", new_theta

			new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)
				#exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, grids.x_max*grids.y_max, new_policy, epochs= 5000, epsilon = 1e-3, gamma=gamma)
				#p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))
			p_B_sum = output_model(grids, starts, new_policy, steps, unsafe, safety)
			print "Policy unsafe rate ", p_B_sum
			#mus = mus + [new_mu]
			#new_mu_B =  counterexample(grids, grids.features, gamma, safety, epsilon)
		if p_B_sum is not None and p_B_sum <= safety:	
			print "Safe, learning from expert"
			mus = mus + [new_mu]
			thetas = thetas + [new_theta]
			policies = policies + [new_policy]
			#if flag is not None and np.linalg.norm(expert - new_mu, ord=2)  < np.linalg.norm(expert - flag['feature'], ord=2):
			if flag is not None and np.dot(new_theta, expert) > np.dot(flag['weight'], expert):
				flag = {'weight': new_theta, 'policy': new_policy, 'value': new_value, 'unsafe': p_B_sum, 'feature': new_mu}
				print "New best candidate"
				print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
				print "Expert can get value ", np.dot(new_theta, expert)
				K_CEX = K
				K = (K + K_EXP)/2
			elif flag is None:
				flag = {'weight': new_theta, 'policy': new_policy, 'value': new_value, 'unsafe': p_B_sum, 'feature': new_mu}
				print "1st best candidate"
				print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
				print "Expert can get value ", np.dot(new_theta, expert)
				K_CEX = K
				K = (K + K_EXP)/2

			else:
				print "Not the best"
				print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
				print "Expert can get value ", np.dot(new_theta, expert)
				K_CEX = K
				K = (K + K_EXP)/2

			print "Add new candidate policy expected feature", new_mu
			
			mu = [[1.0 - K,  K],[mu_Bs, [expert]]]
			#grids, new_theta, new_policy, new_value = expert_train_v1(grids, mu, agent, starts, steps, epsilon=epsilon, iteration=30, gamma=gamma, start_theta= new_theta, MC = False, safety = None)
			new_index, new_theta, w_delta_mu = expert_update_theta_v3(grids, mu, agent, steps, policies, [mus, mus_], gamma, epsilon)
			grids.w_features(new_theta)
			print "Weight learnt from combined feature ", new_theta
			new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)
			#policies = policies + [new_policy]

			p_B_sum = output_model(grids, starts, new_policy, steps, unsafe, safety)
			#exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, grids.x_max*grids.y_max, new_policy, epochs= 5000, epsilon = 1e-3, gamma=gamma)
			#p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))
			print "Policy unsafe rate ", p_B_sum
	

		print "Add uncheck features ", new_mu
	'''
	index, _, w_delta_mu = expert_update_theta(grids, expert, agent, steps, policies, mus, gamma=gamma, epsilon = epsilon)
	print "Iteration ended, best safe theta ", thetas[index]
	print "It's unsafe probability is satisfied"
	print "Distance to expert feature ", w_delta_mu

	return grids, thetas[index], policies[index], w_delta_mu
	'''
	print "Iteration ended, best safe theta ", flag['weight']
	print "It's unsafe probability is ", flag['unsafe']
	print "Distance to expert feature ", np.linalg.norm(expert - flag['feature'], ord= 2)
	return grids, flag['weight'], flag['policy'], flag['value']


def expert_synthesize3(grids, expert, agent, starts, steps, epsilon=1e-6, iteration=100, gamma=0.5, start_theta= None, MC = False, unsafe = None, safety = 0.0001, exp_policy = None):
	print "Human demo feature ", expert
	print "AL learnt theta ", start_theta
	flag = None
	thetas = []
	mu_Bs = []
	mus = []
	mus_ = []
	policies = []	
	grids.w_features(start_theta)
	start_policy, start_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma, toolbox = False, starts = starts)
	#policies = policies + [start_policy]
	new_policy = start_policy
	#return start_theta, start_policy, start_value, None
	if MC is False:
		start_mu, MU = optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
	else:
		exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = epsilon , gamma=gamma, bounds = np.zeros([len(starts)]), unsafe = unsafe)

		start_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 
		
	new_mu = start_mu
	#mus.append(new_mu)
	#expert = np.array(start_mu)
	#print "expert feature changed to ", start_mu

	new_theta = np.array(start_theta)
	#thetas.append(new_theta)
	p_B_sum = output_model(grids, starts, start_policy, steps, unsafe, safety)
	#exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, grids.x_max*grids.y_max, start_policy, epochs= 5000, epsilon = 1e-3, gamma=gamma)
	#p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))
	print "Initial unsafe path rate ", p_B_sum

	print "model output finished for initial policy"
	if p_B_sum <= safety and p_B_sum is not None:
		return grids, start_theta, start_policy, start_value
	elif p_B_sum is None:
		print "Model checking failed"
		return None
	elif p_B_sum > safety:
		new_mu_B =  counterexample(grids, grids.features, gamma, safety, epsilon, steps)
		#new_mu_B = np.sum(np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]), 0) 
		if new_mu_B is not None:
			mu_Bs = mu_Bs + [new_mu_B]
			print "Add counterexample features ", new_mu_B	

	

	while p_B_sum > safety:
		print "Keep generating counterexamples until find a safe candidate" 
		new_mu_B =  counterexample(grids, grids.features, gamma, safety, epsilon, steps)
		#new_mu_B = np.sum(np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]), 0) 
		if new_mu_B is not None:
			if len(mu_Bs) > 2:
				if np.linalg.norm(new_mu_B - mu_Bs[-1], ord=2) < epsilon:
					print "Can't find more diffferent counterexample"
					print "Failed to find safe policy"
					break
			mu_Bs = mu_Bs + [new_mu_B]
			print "Add counterexample features ", new_mu_B	
		elif len(mu_Bs) == 0:
			print "Failed to find counterexample"
			break

		new_index, new_theta, w_delta_mu = expert_update_theta(grids, np.zeros(len(grids.features[-1][-1])), agent, steps, policies, mu_Bs, gamma, epsilon)
		#thetas.append(new_theta)
		if len(thetas) > 2:
			if np.linalg.norm(thetas[-1] - thetas[-2], ord = 2) < epsilon:
				print "Can't find more diffferent counterexample"
				print "Failed to find safe policy"
				break
		grids.w_features(new_theta)
		print "Weight learnt from counterexamples ", new_theta

		new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)

		p_B_sum = output_model(grids, starts, new_policy, steps, unsafe, safety)
		#exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, grids.x_max*grids.y_max, new_policy, epochs= 5000, epsilon = 1e-3, gamma=gamma)
		#p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))
		print "Policy unsafe rate ", p_B_sum

		
	if p_B_sum > safety and exp_policy is not None:
		print "Try a again: Test hand made policy"
		new_theta = -1.0 * np.ones([len(grids.features[-1][-1])]).astype(float)
		new_theta = new_theta/np.linalg.norm(new_theta, ord= 2)
		new_value = None
		new_policy = np.array(exp_policy)
		p_B_sum = output_model(grids, starts, new_policy, steps, unsafe, safety)
		print "Policy unsafe rate ", p_B_sum
	if p_B_sum > safety:
		print "No hope"
		return None

     	print "Found 1st safe policy towards safety ", new_theta	
	if MC is False:
		new_mu, MU = optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
	else:
		exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = epsilon, gamma=gamma, bounds = np.zeros([len(starts)]), unsafe = unsafe)
		new_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 
	print "Corresponding feature ", new_mu
	mus = mus + [new_mu]
	thetas = thetas + [new_theta]
	policies = policies + [new_policy]
	flag = {'weight': new_theta, 'policy': new_policy, 'value': new_value, 'unsafe': p_B_sum, 'feature': new_mu}


	K_EXP = 1.0
	K_CEX = 0.0
	K = 1.0
	mu = [[1.0 - K,  K],[mu_Bs, [expert]]]

	if len(mu_Bs) == 0:
		print "No counterexample found"
		return None
		
	new_index, new_theta, w_delta_mu = expert_update_theta(grids, expert, agent, steps, policies, mus, gamma, epsilon)
	grids.w_features(new_theta)
	print "Weight learnt from 1st combined feature ", new_theta
	
	new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)
	#exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, grids.x_max*grids.y_max, new_policy, epochs= 5000, epsilon = 1e-3, gamma=gamma)
	#p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))
	p_B_sum = output_model(grids, starts, new_policy, steps, unsafe, safety)
	print "Policy unsafe rate ", p_B_sum
	while True:
		print "Learning under same k"
		if p_B_sum <= safety:
			if MC is False:
				new_mu, MU = optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
			else:
				exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = epsilon, gamma=gamma, bounds = np.zeros([len(starts)]), unsafe = unsafe)
				new_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 
			if np.linalg.norm(mus[-1] - new_mu, ord = 2) > epsilon:
				print "Same k, found safe policy"
				mus = mus + [new_mu]
				thetas = thetas + [new_theta]
				policies = policies + [new_policy]
			else:
				mus = mus + [new_mu]
				thetas = thetas + [new_theta]
				policies = policies + [new_policy]
				print "Can't find more safe policy"
				#break
			if flag is not None and np.dot(new_theta, expert) > np.dot(flag['weight'], expert):
			#if flag is not None and np.linalg.norm(expert - new_mu, ord=2)  < np.linalg.norm(expert - flag['feature'], ord=2):
				flag = {'weight': new_theta, 'policy': new_policy, 'value': new_value, 'unsafe': p_B_sum, 'feature': new_mu}
				print "New best candidate"
				print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
				print "Expert can get value ", np.dot(new_theta, expert)
			else:
				print "Not the best"
		elif p_B_sum > safety:
			new_mu_B =  counterexample(grids, grids.features, gamma, safety, epsilon, steps)
			if new_mu_B is None:
				#return grids, flag['weight'], flag['policy'], flag['value']
				print "Can't find counterexample"
				break
			ignore = False
			for e in mu_Bs:
				if np.linalg.norm(new_mu_B - mu_Bs[-1], ord =2) < epsilon:
					print "Can't find more different counterexample"
					ignore = True
					break
			if ignore is False:
				print "Same k, found different counterexample"
				mu_Bs = mu_Bs + [new_mu_B]	
			else:
				break
		if p_B_sum < safety:
			print "Can't find more safe policies"
			iteration = 0		
		else:	
			iteration = 1
		mu = [[1.0 - K,  K],[mu_Bs, [expert]]]
		new_index, new_theta, w_delta_mu = expert_update_theta_v2(grids, mu, agent, steps, policies, mus, gamma, epsilon)
		grids.w_features(new_theta)
		print "Weight learnt from combined feature ", new_theta
		new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)
		p_B_sum = output_model(grids, starts, new_policy, steps, unsafe, safety)
		print "Policy unsafe rate ", p_B_sum

	while iteration > 0:
		print ">>>>>>>>> ", iteration, "th iteration\n", "candidate theta: ", new_theta, "\nunsafe probability:", p_B_sum, "\nfeature ", new_mu, " = ", 1.0 - K, "*safe + ", K, "*expert\n" 
		file = open('log', 'a')
		file.write(">>>>>>>>> " + str(iteration) + "th iteration, candidate theta: "+ str(new_theta) + "; unsafe probability: " + str(p_B_sum) + "; feature " + str(new_mu) + " = " + str(1.0 - K) + "*safe + " + str(K) + "*expert\n") 
		file.close()
		iteration = iteration + 1
		
		if iteration >= 20:
			break
		
		if abs(K_CEX - K_EXP) < 1.0:
			if abs(K_CEX - K) < epsilon or abs(K_EXP - K) < epsilon:
				print ">>>>>>>>>>>>>>>Convergeed<<<<<<<<<<<<<<<<"
				break
				if len(mus) >= 2:
					if np.linalg.norm(mus[-1] - mus[-2], ord = 2) < epsilon:
						print ">>>>>>>>>>>>>>>Convergeed<<<<<<<<<<<<<<<<"
						break
				if len(mu_Bs) >= 2:
					if  np.linalg.norm(mu_Bs[-1] - mu_Bs[-2], ord = 2) < epsilon:
						print ">>>>>>>>>>>>>>>Convergeed<<<<<<<<<<<<<<<<"
						break
			#print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
			#print "Expert can get value ", np.dot(theta, expertw)
			#flag = [new_theta, new_policy, new_value, new_mu]
			#return grids, flag[0], flag[1], flag[2]
		if p_B_sum is not None and p_B_sum > safety:
			print "Unsafe, learning from counterexample"
			#while p_B_sum > safety:
			#new_mu_B = np.sum(np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]), 0) 
			#new_mu_B =  counterexample(grids, grids.features, gamma, safety, epsilon, steps)
			#if new_mu_B is not None:
			#	mu_Bs = mu_Bs + [new_mu_B]
			#	print "Add counterexample features ", new_mu_B	
			#if new_mu_B is None:
			#	print "Can't find more different counterexample"
				#break
				#return grids, flag['weight'], flag['policy'], flag['value']

			while p_B_sum > safety:
				print "Learning under same k"
				new_mu_B =  counterexample(grids, grids.features, gamma, safety, epsilon, steps)
				if new_mu_B is None:
					#return grids, flag['weight'], flag['policy'], flag['value']
					print "Somehow can't find more different counterexample"
					break
				ignore = False
				for e in mu_Bs:
					if np.linalg.norm(new_mu_B - mu_Bs[-1], ord =2) < epsilon:
						print "Can't find more different counterexample"
						ignore = True
						break
				if ignore is False:
					print "Same k, found different counterexample"
					mu_Bs = mu_Bs + [new_mu_B]	
				else:
					break
				mu = [[1.0 - K,  K],[mu_Bs, [expert]]]
				new_index, new_theta, w_delta_mu = expert_update_theta_v2(grids, mu, agent, steps, policies, mus, gamma, epsilon)
				grids.w_features(new_theta)
				print "Weight learnt from combined feature ", new_theta
				new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)
				p_B_sum = output_model(grids, starts, new_policy, steps, unsafe, safety)
				print "Policy unsafe rate ", p_B_sum
			if p_B_sum > safety:
				#KK = k
				#k = (K + KK)/2			
				#K_EXP = K
				K = (K + K_CEX)/2.0
			mu = [[1.0 - K,  K],[mu_Bs, [expert]]]
			new_index, new_theta, w_delta_mu = expert_update_theta_v2(grids, mu, agent, steps, policies, mus, gamma, epsilon)
			grids.w_features(new_theta)
			print "Weight learnt from combined feature ", new_theta

			new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)
				#exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, grids.x_max*grids.y_max, new_policy, epochs= 5000, epsilon = 1e-3, gamma=gamma)
				#p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))
			p_B_sum = output_model(grids, starts, new_policy, steps, unsafe, safety)
			print "Policy unsafe rate ", p_B_sum
			#mus = mus + [new_mu]
			#new_mu_B =  counterexample(grids, grids.features, gamma, safety, epsilon)
		if p_B_sum is not None and p_B_sum <= safety:	
			print "Safe, learning from expert"
			if MC is False:
				new_mu, MU = optimal_feature(grids, starts, steps, new_policy, epsilon = epsilon, gamma=gamma)
			else:
				exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, steps, new_policy, epochs= 5000, epsilon = epsilon, gamma=gamma, bounds = np.zeros([len(starts)]), unsafe = unsafe)
				new_mu = np.sum(np.reshape(exp_u_G, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_G, [grids.y_max*grids.x_max, 1]) +   np.reshape(exp_u_B, [grids.y_max*grids.x_max, len(grids.features[-1][-1])]) * np.reshape(p_B, [grids.y_max*grids.x_max, 1]), 0) 
			print "Corresponding feature ", new_mu
			mus = mus + [new_mu]
			thetas = thetas + [new_theta]
			policies = policies + [new_policy]
			#if flag is not None and np.linalg.norm(expert - new_mu, ord=2)  < np.linalg.norm(expert - flag['feature'], ord=2):
			if flag is not None and np.dot(new_theta, expert) > np.dot(flag['weight'], expert):
				flag = {'weight': new_theta, 'policy': new_policy, 'value': new_value, 'unsafe': p_B_sum, 'feature': new_mu}
				print "New best candidate"
				print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
				print "Expert can get value ", np.dot(new_theta, expert)
				K_CEX = K
				K = (K + K_EXP)/2
			elif flag is None:
				flag = {'weight': new_theta, 'policy': new_policy, 'value': new_value, 'unsafe': p_B_sum, 'feature': new_mu}
				print "1st best candidate"
				print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
				print "Expert can get value ", np.dot(new_theta, expert)
				K_CEX = K
				K = (K + K_EXP)/2

			else:
				print "Not the best"
				print "Feature deviation from expert ", np.linalg.norm(new_mu - expert, ord = 2)
				print "Expert can get value ", np.dot(new_theta, expert)
				K_CEX = K
				K = (K + K_EXP)/2

			print "Add new candidate policy expected feature", new_mu
			
			mu = [[1.0 - K,  K],[mu_Bs, [expert]]]
			#grids, new_theta, new_policy, new_value = expert_train_v1(grids, mu, agent, starts, steps, epsilon=epsilon, iteration=30, gamma=gamma, start_theta= new_theta, MC = False, safety = None)
			new_index, new_theta, w_delta_mu = expert_update_theta_v2(grids, mu, agent, steps, policies, mus, gamma, epsilon)
			grids.w_features(new_theta)
			print "Weight learnt from combined feature ", new_theta
			new_policy, new_value = optimal_value(grids, agent, steps = steps, epsilon=epsilon, gamma = gamma)
			#policies = policies + [new_policy]

			p_B_sum = output_model(grids, starts, new_policy, steps, unsafe, safety)
			#exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(grids, agent, starts, grids.x_max*grids.y_max, new_policy, epochs= 5000, epsilon = 1e-3, gamma=gamma)
			#p_B_sum = np.sum(np.reshape(p_B, [grids.y_max*grids.x_max]))/(len(starts))
			print "Policy unsafe rate ", p_B_sum
	

	index, _, w_delta_mu = expert_update_theta(grids, expert, agent, steps, policies, mus, gamma=gamma, epsilon = epsilon)


	print "Iteration ended, best safe theta ", thetas[index]
	print "It's unsafe probability is satisfied"
	print "Distance to expert feature ", w_delta_mu

	return grids, thetas[index], policies[index], w_delta_mu
def counterexample(grids, mu, gamma = 0.99, safety = 0.01, epsilon = 1e-5, steps = 64):
	safety_ = safety
	print "Removing last counterexample file"
	os.system('rm counter_example.path')
	#while safety_ > safety * epsilon**2 :
	while safety_ > 1e-15:
		file = open('grid_world.conf', 'w')
		file.write('TASK counterexample\n')
		file.write('PROBABILITY_BOUND ' + str(safety_) + '\n')
		file.write('DTMC_FILE ./grid_world.dtmc' + '\n')
		file.write('REPRESENTATION pathset' + '\n')
		file.write('SEARCH_ALGORITHM global' + '\n')
		file.write('ABSTRACTION concrete' + '\n')
		file.close()
		cex_comics_timer(['sh', '/home/zekunzhou/workspace/Safety-AI-MDP/saapirl/comics-1.0/comics.sh', './grid_world.conf'], 2)
		try:
			file = open('counter_example.path', 'r')
			break
		except:
			print "No counterexample found for spec = ", safety_, "shrinking down the safey"
			file = None
			safety_ = safety_ / 2.0
	#if safety_ <= safety * epsilon**2:
	if file is None:
		return None
	print "Generated counterexample for ", safety_
	mu_cex = np.zeros(len(grids.features[-1][-1]))
	total_p = 0
	paths = []
	path_strings = []
	lines = file.readlines()
	file.close()
	for line in range(len(lines)-1):
		path_strings.append(lines[line].split(' ')[0].split('->'))
	for path_string in range(len(path_strings)):
		path = []
		path.append(float(lines[path_string].split(' ')[2].split(')')[0]))
		for state_string in path_strings[path_string]:
			if int(state_string) > grids.y_max * grids.x_max - 1:
				continue
			else:
				path.append(int(state_string))
		paths.append(path)
	for path in range(len(paths)):
		p = paths[path][0]
		mu_path = np.zeros(len(grids.features[-1][-1]))
		for state in range(1, len(paths[path])):
			y = paths[path][state]/grids.x_max
			x = paths[path][state]%grids.x_max
			mu_path = mu_path + (gamma**(state - 1)) * grids.features[y][x] 
		length = len(paths[path]) - 1
		y = paths[path][length]/grids.x_max
		x = paths[path][length]%grids.x_max
		while gamma**(length - 1)  > epsilon and steps >= length:
			mu_path = mu_path + (gamma**(length - 1)) * mu[y][x]
			length = length + 1
		mu_cex = mu_cex + p * mu_path
		total_p = total_p + p
	print "Counterexample for spec = ", safety, ": ",total_p
	print "Counterexample feature ", mu_cex
	mu_cex = mu_cex/total_p
	print "Normalized Counterexample feature ", mu_cex
	#os.system('rm counter_example.path')
	return mu_cex		

def output_model(grids, starts, policy, steps = None, unsafe = None, safety = 0.01):
	if steps is None:
		steps  = grids.y_max * grids.x_max
	P = grids.pi_transitions(policy, 1.0)
	transitions = []
	transitions_ = []
	targets = []
	initial = grids.y_max*grids.x_max
	end = grids.y_max*grids.x_max + 1
	
	if unsafe is None:
		unsafe = grids.feature_states[1]
	for state in unsafe:
		targets.append(state[0] * grids.x_max + state[1])

	for i in range(grids.y_max * grids.x_max):
		p_sum = 0.0
		for target in targets:
			if i == target:
				p_sum = 1.0
				break
		if p_sum == 1.0:
			transitions.append(str(i) + ' ' + str(end) + ' ' + str(p_sum) + '\n')
			transitions_.append(str(i) + ' ' + str(end) + ' ' + str(p_sum) + '\n')
		else: 
			if p_sum != 0.0:
				print "Go fuck yourself"
				return None
			y = i / grids.x_max
			x = i % grids.x_max
			for j in range(grids.y_max * grids.x_max): 	
				#if i != j:
				y_ = j / grids.x_max
				x_ = j % grids.x_max
				p = P[y, x, y_, x_]
				transitions.append(str(i) + ' ' + str(j) + ' ' + str(p) + '\n')
				transitions_.append(str(i) + ' ' + str(j) + ' ' + str(p) + '\n')
				p_sum += p
					
			
		#if p_sum < 1.0:
		#	p = 1.0 - p_sum
		#	transitions_.append(str(i) + ' ' + str(i) + ' ' + str(p) + '\n')
		#	transitions.append(str(i) + ' ' + str(i) + ' ' + str(p) + '\n')
		#	p_sum += p

		#if p_sum > 1.0:
		#	print "Error: transition prob sum > 1.0 by ", p_sum
		#	return None
			
				
	for start in starts:
		transitions_.append(str(initial) + ' ' + str(start[0] * grids.x_max + start[1]) + ' ' + str(float(1.0/len(starts))) + '\n')

	transitions_.append(str(end) + ' ' + str(end) + ' ' + str(float(1.0)) + '\n')
	

	file = open('grid_world.conf', 'w')
	file.write('TASK counterexample\n')
	file.write('PROBABILITY_BOUND ' + str(safety) + '\n')
	file.write('DTMC_FILE ./grid_world.dtmc' + '\n')
	file.write('REPRESENTATION pathset' + '\n')
	file.write('SEARCH_ALGORITHM global' + '\n')
	file.write('ABSTRACTION concrete' + '\n')
	file.close()
	'''	
	file = open('grid_world.dtmc', 'w')
	file.write('STATES ' + str(2 + grids.y_max * grids.x_max) + '\n')
	file.write('TRANSITIONS ' + str(len(transitions_)) + '\n')
	file.write('INITIAL ' + str(initial) + '\n')

	#for target in range(len(targets)):
	#	file.write('TARGET ' + str(targets[target]) + '\n')
	file.write('TARGET ' + str(end) + '\n')

	for transition in transitions_:
		file.write(transition)
	file.close()
	#prob = model_check_comics_timer()
	'''
	file = open('state_space', 'w')
	file.write("x_max\n")
	file.write(str(grids.x_max))
	file.write("\ny_max\n")
	file.write(str(grids.y_max))
	file.write("\nactions\n")
	file.write(str(grids.actions))
	file.close()

	file = open('optimal_policy', 'w')
	for transition in transitions_:
		file.write(transition)
	file.close()

	file = open('unsafe', 'w')
	for state in unsafe:
		file.write(str(state[0]) + ':' + str(state[1]) + '\n')
	file.close()


	prob = 0.0
	'''
	##add initial states one by one in each loop
	for start in range(0, len(starts)):
		os.system('export DIR=/home/zekunzhou/workspace/Safety-AI-MDP/saapirl')
		os.system('/home/zekunzhou/workspace/Safety-AI-MDP/saapirl/prism-4.4.beta-src/src/demos/run')
		file = open('grid_world.pm', 'a')
		file.write("\ninit (x = " + str(starts[start][1]) + "& y = " + str(starts[start][0]) + ") endinit\n")
		file.close()
		file = open('grid_world.pctl', 'w')
		file.write('P=?[true U<=' + str(steps))
		file.write(' (x=' + str(unsafe[0][1]) + '&y=' + str(unsafe[0][0]) + ')')
		for target in range(1, len(targets)):
			 file.write('|(x=' + str(unsafe[target][1]) + '&y=' + str(unsafe[target][0]) + ')')
		#file.write('| (x > 0 & y <  x & x < 5)')
		file.write(']')
		file.close()
		prob += model_check_prism()
	prob /= len(starts)
	'''
	##add one extra initial state which directs to all real initial states with probabilities
	os.system('export DIR=/home/zekunzhou/workspace/Safety-AI-MDP/saapirl')
	os.system('/home/zekunzhou/workspace/Safety-AI-MDP/saapirl/prism-4.4.beta-src/src/demos/run /home/zekunzhou/workspace/Safety-AI-MDP/saapirl')
	#os.system('/home/zekunzhou/workspace/Safety-AI-MDP/saapirl/prism-4.4.beta-src/src/demos/run')
	#file = open('grid_world.pm', 'a')
	#file.write("\ninit (x = " + str(0) + "& y = " + str(grids.y_max) + ") endinit\n")
	#file.close()
	file = open('grid_world.pctl', 'w')
	file.write('P=?[true U<=' + str(steps))
	file.write(' (x=' + str(int(end%grids.x_max)) + '&y=' + str(int(end/grids.x_max)) + ')')
	#file.write(' (x=' + str(unsafe[0][1]) + '&y=' + str(unsafe[0][0]) + ')')
	#for target in range(1, len(targets)):
	#	 file.write('|(x=' + str(unsafe[target][1]) + '&y=' + str(unsafe[target][0]) + ')')
	#file.write('| (x > 0 & y <  x & x < 5)')
	file.write(']')
	file.close()
	prob += model_check_prism()
	if prob is not None:
		return prob
	else:
		print "Probability is None"
		return None

def model_check_prism(cmd = ['/home/zekunzhou/workspace/Safety-AI-MDP/saapirl/prism-4.4.beta-src/bin/prism', './grid_world.pm', './grid_world.pctl'], timeout_sec = 5.0):
	kill_proc = lambda p: p.kill()
  	proc = subprocess.Popen(cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
  	timer = Timer(timeout_sec, kill_proc, [proc])
	probs = []
	prob = 0.0
  	try:
    		timer.start()
   	 	stdout, stderr = proc.communicate()
  	finally:
    		timer.cancel()
  		try:
			lines = "".join(stdout).split('\n')
			for line in lines:
				if line.split(':')[0] == 'Result':
					prob_strs =  re.split('\[|\]| |,', line.split(':')[1].split('(')[0])
					for prob_str in prob_strs:
						if prob_str != '' and prob_str != ' ':
							probs.append(float(prob_str))
					break
			#prob = float("".join(stdout).split('\n')[-7].split(' ')[1])
			for p in probs:
				prob += p
			prob /= len(probs)
  			return prob
		except:
			print "PRISM model checking failed, return None"
			return None
	
	
		
def model_check_comics_timer(cmd = ['sh', '/home/zekunzhou/workspace/Safety-AI-MDP/saapirl/comics-1.0/comics.sh', './grid_world.conf', '--only_model_checking'], timeout_sec = 10.0):
  	kill_proc = lambda p: os.system('kill -9 $(pidof comics)')
  	proc = subprocess.Popen(cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
  	timer = Timer(timeout_sec, kill_proc, [proc])
  	try:
    		timer.start()
   	 	stdout, stderr = proc.communicate()
  	finally:
    		timer.cancel()
		#print stdout
		print stderr	
  		try:
			prob = float("".join(stdout).split('\n')[-2].split(':')[-1])
			if prob <= 1.0:
  				return prob
		except:
    			prob = float("".join(stdout).split('\n')[-3].split(':')[-2].split(";")[0])
			if prob <= 1.0:
				return prob
		return None

  	
def cex_comics_timer(cmd = ['sh', '/home/zekunzhou/workspace/Safety-AI-MDP/saapirl/comics-1.0/comics.sh', './grid_world.conf'], timeout_sec = 5.0):
  	kill_proc = lambda p: os.system('kill -9 $(pidof comics)')
  	proc = subprocess.Popen(cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
  	timer = Timer(timeout_sec, kill_proc, [proc])
  	try:
    		timer.start()
   	 	stdout, stderr = proc.communicate()
  	finally:
    		timer.cancel()
		#print stdout
		print stderr	


	
class train:
	def __init__(self, grids= grid(12, 12, 0.6), starts = None, steps = float("inf"), epsilon = 1e-4, gamma = 0.6, iteration = 30, theta = None):
		if theta is None:
			theta = np.random.randint(100, size = len(grids.features[-1][-1]))
			theta = np.array(theta).astype/np.linalg.norm(theta, ord=2)
		if steps is None:
			self.steps= float("inf")
		else:
			self.steps = steps
		self.iteration = iteration
		self.epsilon = epsilon
		self.gamma = gamma	
		self.grids=grids
		self.expert= []
		self.expert_policy = np.zeros([self.grids.y_max, self.grids.x_max])
		self.demo_policy = np.zeros([self.grids.y_max, self.grids.x_max])
		self.agent=car(states=self.grids.states)
		self.theta = np.array(theta)
		self.starts = starts
		#pylab.ioff()
	def reinforce_synthesize(self, theta, starts= None, epsilon= None, unsafe = None, safety = 0.01):
		demo_mu = np.array([  57.58416513,  58.19742098,   1.10344096,   1.43110657])
		theta = np.array( [  0.75168159,  0.65815897,  0.0338108,   0.02565913])
		if unsafe is None:
			unsafe = self.grids.feature_states[1]
		if epsilon is None:
			epsilon = self.epsilon
		if theta is None:
			theta = self.theta
		theta = theta / np.linalg.norm(theta, ord = 2)
		i = 1
		learnt_theta = np.array(theta).astype(float)/np.linalg.norm(theta, ord=2)
		learnt_policy, learnt_mu = real_optimal(self.grids, self.agent, starts = starts, steps = self.steps, theta = theta, gamma = self.gamma, epsilon = epsilon)
		last_margin = float('inf')
		margin = 0.0
		while i < 10 and abs(last_margin - margin) > epsilon:
			last_margin = np.array(margin)
			last_theta = np.array(learnt_theta)
			_, learnt_theta, learnt_policy, learnt_prob = expert_synthesize(self.grids, demo_mu, self.agent, epsilon = epsilon, starts = starts, steps= self.steps, iteration = self.iteration, gamma=self.gamma, start_theta = theta, MC = False, unsafe = unsafe, safety = safety, exp_policy = learnt_policy)
			if learnt_theta is not None:
				self.grids.w_features(learnt_theta)
				learnt_mu, _  = optimal_feature(self.grids, starts, self.steps, learnt_policy, epsilon = self.epsilon, gamma=self.gamma)
			else:
				learnt_theta = np.array(last_theta)
			margin = np.linalg.norm(learnt_mu - demo_mu, ord = 2)
			file = open('log', 'a')
			file.write(str(i) +"st reinforce synthesize, safety " + str(safety) + ", weight " + str(learnt_theta) + ", prob " + str(learnt_prob) + ", margin " + str(margin) + "\n\n\n")
			print str(i) +"st reinforce synthesize, safety " + str(safety) + ", weight " + str(learnt_theta) + ", prob " + str(learnt_prob) + ", margin " + str(margin) + "\n"
			file.close()
			i += 1

		
	def synthesize(self, theta, starts= None, epsilon= None, unsafe = None, safety = 0.01):
		if unsafe is None:
			unsafe = self.grids.feature_states[1]
		if epsilon is None:
			epsilon = self.epsilon
		policies = []
		mus = []
		exp_mu = np.zeros(len(self.grids.features[-1][-1]))	
		if theta is None:
			theta = self.theta
		#For 0.1
		#theta = np.array([0.12741171,  0.13864167, -0.69381431, -0.69510175])
		#For 0.8
		#theta = np.array([ 0.0653951,   0.07745992, -0.7005758,  -0.70634057])

		theta = np.array(theta).astype(float)/np.linalg.norm(theta, ord=2)
		print theta
		self.grids.w_features(theta)
		#draw_grids(self.grids.rewards, None)
	
		self.expert_policy, exp_mu = real_optimal(self.grids, self.agent, starts = starts, steps = self.steps, theta = theta, gamma = self.gamma, epsilon = epsilon)
		print "real optimal policy"
		print self.expert_policy
		print "real expected feature under optimal policy"
		print exp_mu
		demo_mu = exp_mu
		
		start = time.time()
		prob = output_model(self.grids, starts, self.expert_policy, self.steps, unsafe, safety)
		new_mu_B =  counterexample(self.grids, self.grids.features, self.gamma, safety, self.epsilon, self.steps)
		print "Optimal policy unsafe probability ", prob
		end = time.time()
		optimal_feature(self.grids, starts, self.steps, self.expert_policy, epsilon = self.epsilon, gamma=self.gamma)
		'''
		file = open('log', 'a')
		file.write(str(self.grids.y_max * self.grids.x_max) + " model checking " + str(end - start) + "\n")
		print(str(self.grids.y_max * self.grids.x_max) + " model checking " + str(end - start) + "\n")
		file.close()

		start = time.time()
		exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(self.grids, self.agent, starts, self.steps, self.expert_policy, epochs= 8000, epsilon = self.epsilon , gamma=self.gamma, bounds = np.zeros([len(starts)]), unsafe = unsafe)
		demo_mu = np.sum(np.reshape(exp_u_G, [self.grids.y_max*self.grids.x_max, len(self.grids.features[-1][-1])]) * np.reshape(p_G, [self.grids.y_max*self.grids.x_max, 1]) +   np.reshape(exp_u_B, [self.grids.y_max*self.grids.x_max, len(self.grids.features[-1][-1])]) * np.reshape(p_B, [self.grids.y_max*self.grids.x_max, 1]), 0) 
		new_mu_B = np.sum(np.reshape(exp_u_B, [self.grids.y_max*self.grids.x_max, len(self.grids.features[-1][-1])]), 0) 
		p_B_sum = np.sum(np.reshape(p_B, [self.grids.y_max*self.grids.x_max]))/(len(starts))
		end = time.time()
		file = open('log', 'a')
		file.write(str(self.grids.y_max * self.grids.x_max) + " Monte Carlo " + str(end - start) + "\n")
		print(str(self.grids.y_max * self.grids.x_max) + " Monte Carlo " + str(end - start) + "\n")
		file.close()
		'''

		#print "unsafe path feature ", np.sum(np.reshape(exp_u_B, [self.grids.y_max * self.grids.x_max, len(self.grids.features[-1][-1])]), 0)
		#demo_mu = optimal_feature(self.grids, starts, self.steps, self.demo_policy, epsilon = self.epsilon, gamma=self.gamma)
		#For [3 ,3], [6, 6], [4, 4], [7, 7]
		#demo_mu = np.array([ 40.89036619,   0.64147873,   9.98327114,   0.])
		#demo_mu = np.array([ 39.20935148,  52.6594597,   12.72442136,  12.82155975])
		#theta = np.array([ 0.66812298,  0.70314324,  0.17274471,  0.17134912])
		#For [3, 7], [7,3], [5, 5], [7, 7]
		#demo_mu = np.array([ 44.075131,    43.41778817,   5.40566983,   1.61532099])
		#demo_mu = np.array([ 44.075131,    43.41778817,   5.40566983,  0.0])
		#For [3, 7], [1, 6], [1, 3], [6, 5]
		#demo_mu = np.array([49.06798858,  50.84211635,   3.93830203,   0.        ])
		#theta = np.array([0.69683357, 0.71605115, 0.04115484, 0.0])
		#For [3, 7], [1, 6], [1, 3], [4, 4]
		#demo_mu = np.array([ 22.40729888,  62.27166007,   5.2054007,    2.57517056])
		#theta = np.array([ 0.70259415,  0.69168086, -0.06375435,  0.15451353])

		#For [1, 7], [7, 2], [3, 3], [4, 4]
		#demo_mu = np.array([44.79990088, 45.11285122,   1.60969386,   0.        ])	
		#safety = 0.01
		#theta = np.array([ 0.71021283,  0.70381664, -0.01548792,  0.])
		#For [2, 6], [1, 6], [3, 3], [4, 4]
		#demo_mu = np.array([ 63.22198067,  63.41995431,   3.7295239,    0.        ])
		#For [7, 7], [7, 6], [4, 4], [4, 6]
		#demo_mu = np.array([ 53.45346621,  51.51237465,   3.10056466,   5.0122147 ])
		#For [7, 7], [7, 6], [4, 6], [5, 3]
		#demo_mu = np.array([ 58.95770271,  59.17225335,   3.50161782,   3.86107397])
		#For [7, 7], [7, 6], [4, 6], [6, 1]
		#demo_mu = np.array([ 57.8561493,   57.68399681,   3.19279245,   4.25976904])
		#theta = np.array([ 0.72613264,  0.64114756, -0.05041496,  0.24314507])
		#For [7, 7], [7, 6], [1, 7], [7, 1] +++++
		#demo_mu = np.array([ 58.58578586,  60.18166551,   0.22654301,   1.3339427 ])
		#theta = np.array( [ 0.7489454,   0.66060699, -0.00105728,  0.0517501 ])
		#For [7, 7], [7, 6], [2, 6], [6, 2] +++++
		demo_mu = np.array([  57.58416513,  58.19742098,   1.10344096,   1.43110657])
		theta = np.array( [  0.75168159,  0.65815897,  0.0338108,   0.02565913])
		
		#safety = 0.4
		#self.demo_policy, _  = real_optimal(self.grids, self.agent, starts = starts, steps = self.steps, theta = theta, gamma = self.gamma, epsilon = epsilon)
		#safety = 0.01
		print "safety requirement is ", safety
		
		'''
		if starts is None:
			starts = np.array(self.starts)
		if epsilon is None:
			epsilon = self.epsilon
		again = 'y'
		while(again != 'n' and again!= 'n'):
			if again != 'y' and again!= 'y':
				print "invalid input, exit...??"
				break
			else:
				start=starts[random.randint(0, len(starts)-1)]
				expert_temp, again = demo(self.grids, self.agent, start, theta = theta, steps= self.steps, gamma=self.gamma, epsilon= epsilon)
				self.expert.append(expert_temp)
		starts = []
		print "start training..."
			
		demo_mu = np.zeros(len(self.grids.features[-1][-1]))
		for i in range(len(self.expert)):
			demo_mu = demo_mu + self.expert[i]["mu"] 
			starts.append(self.expert[i]["trajectory"][0]["state"])
		demo_mu = demo_mu/len(self.expert)	
		print "expected demo mu is ", demo_mu
		_, theta, self.demo_policy,_ = expert_train(self.grids, demo_mu, self.agent, epsilon = epsilon, starts = starts, steps= self.steps, iteration = 10, gamma=self.gamma, start_theta = None, MC = False)
		print "theta learnt from demo mu ", theta
		file = open('log', 'a')	
		file.write("\nlearnt from human demo before ultimate synthesis\n")
		for i in self.grids.feature_states:
			file.write(str(i))
		file.write("\n")
		#file.write(str(self.grids.loc_max_0))
                #file.write(str(self.grids.loc_max_1))
                #file.write(str(self.grids.loc_min_0))
                #file.write(str(self.grids.loc_min_1)+'\n')

		file.write("parameter "+ str(theta) + "\n")
		for i in self.demo_policy:
			for j in i:
				file.write(str(j)+":")
			file.write("\n")
		file.write("\n")
		'''
		
		_, theta, self.demo_policy,_ = MC_synthesize(self.grids, demo_mu, self.agent, epsilon = epsilon, starts = starts, steps= self.steps, iteration = self.iteration, gamma=self.gamma, start_theta = theta, MC = True, unsafe = unsafe, safety = safety, exp_policy = None)
		self.grids.w_features(theta)
		draw_grids(self.grids.rewards, None)
		file = open('log', 'a')	
		file.write("\nleanrt from ultimate synthesis\n")
		for i in self.grids.feature_states:
			file.write(str(i))
		file.write("\n")
		#file.write(str(self.grids.loc_max_0))
                #file.write(str(self.grids.loc_max_1))
                #file.write(str(self.grids.oc_min_0))
                #file.write(str(self.grids.loc_min_1)+'\n')

		file.write("parameter "+ str(theta) + "\n")
		for i in self.demo_policy:
			for j in i:
				file.write(str(j)+":")
			file.write("\n")
		file.write("feature " + str(demo_mu) + "\n")
		print self.demo_policy



 	def learn_from_policy(self, starts = None, expert_policy = None, safety = True):
		if starts is None:
			starts = np.array(self.starts)
		if expert_policy is not None:
			self.expert_policy = expert_policy
		else:
			i = 0
                        j = 0
                        file = open('demo_policy', 'r')
                        for line in file:
                                for j in range(len(line.split(":"))-1):
                                       	self.expert_policy[i, j] = float(line.split(":")[j])
                                i = i + 1
                        file.close()
		
		print self.expert_policy	

		
		file=open('log', 'a')
		file.write("learn from human policy\n")
		
		for i in self.grids.feature_states:
			file.write(str(i))
		file.write("\n")
		#file.write(str(self.grids.loc_max_0))
                #file.write(str(self.grids.loc_max_1))
                #file.write(str(self.grids.loc_min_0))
                #file.write(str(self.grids.loc_min_1)+'\n')

		for i in range(len(self.expert_policy)):
			for j in range(len(self.expert_policy[i])):
				file.write(str(self.expert_policy[i, j]) + ":")
			file.write("\n")
		exp_mu = optimal_feature(self.grids, starts, self.steps, self.expert_policy, epsilon = self.epsilon, gamma=self.gamma)
		print "analytical feature" + str(exp_mu)
		if safety is True:
                	exp_u_g, p_g, exp_u_b, p_b, _ = sample_feature(self.grids, self.agent, starts, self.steps, self.expert_policy, epochs= 10000, epsilon = self.epsilon, gamma=self.gamma)
			print exp_u_g[0][0]
                        p_b_expert = np.sum(np.reshape(p_b, [self.grids.y_max*self.grids.x_max]))/(len(starts))
			mu_b = np.sum(np.reshape(exp_u_b, [self.grids.y_max*self.grids.x_max, len(self.grids.features[-1][-1])])* np.reshape(p_b, [self.grids.y_max*self.grids.x_max, 1]), 0)
			mu_g = np.sum(np.reshape(exp_u_g, [self.grids.y_max*self.grids.x_max, len(self.grids.features[-1][-1])]), 0)
			print "expected failure path feature ", mu_b
			print "expected successful path feature ", mu_g
			exp_mu = mu_g
		#exp_u_g, p_g, exp_u_b, p_b = sample_feature(self.grids, self.agent, starts, self.grids.x_max * self.grids.y_max, self.expert_policy, epochs= 5000, epsilon = 1e-3, gamma=self.gamma)
		#exp_mu = np.sum(np.reshape(exp_u_g, [self.grids.y_max * self.grids.x_max, len(self.grids.features[-1][-1])]), 0)
		#print "monte carlo " + str(exp_mu)
		file.write(str(exp_mu) + '\n')
		file.close()	
	
		_, theta, policy, _= expert_train(self.grids, exp_mu, self.agent, starts = starts, steps= self.steps, epsilon= self.epsilon, iteration=self.iteration, gamma=self.gamma, start_theta= None, MC = False, safety = None)
		for i in range(len(policy)):
			for j in range(len(policy[i])):
				if policy[i, j] != self.expert_policy[i, j]:
					print "feature matched policy is different with expert"
					'''
					exp_u_g, p_g, exp_u_b, p_b = sample_feature(self.grids, self.agent, starts, self.steps, policy, epochs= 5000, epsilon = self.epsilon, gamma=self.gamma)
					p_b_sum = np.sum(np.reshape(p_b, [self.grids.y_max*self.grids.x_max]))/(len(starts))
					print "feature matched policy unsafe rate ", p_b_sum						   '''
					file = open('log', 'a')
					file.write("learnt policy is different\n")
					#file.write(str(p_b_expert)+'\n')	
					file.write(str(theta)+'\n')
					for i in policy:
						for j in i:
							file.write(str(j)+":")
						file.write("\n")
					#file.write(str(p_b_sum)+'\n')
				
					file.close()
					return policy
		print "precisely learnt"
		file = open('log', 'a')
		file.write("precisely learnt\n")
		file.close()
		return policy

		

	def real_expert_train(self, starts = None, expert_theta = None, epsilon= None, distribution= None, safety = True):
		if distribution is None:
			distribution = [1.0]

		if starts is None:
			if self.starts is None:
				starts = [np.array([0, 0])]
			else:
				starts = self.starts
		if epsilon is None:
			epsilon = self.epsilon
		if expert_theta is None:
			expert_theta = self.theta/np.linalg.norm(self.theta, ord=2)
		else:
			expert_theta = expert_theta/np.linalg.norm(expert_theta, ord=2)
		#print "feature states are "+ str(self.grids.loc_max_0)+str(self.grids.loc_max_1)+str(self.grids.loc_min_0)+str(self.grids.loc_min_1)
		print "ground true weight is ", expert_theta
		self.expert_policy, exp_mu =real_optimal(self.grids, self.agent, starts = starts,  steps = self.steps, theta = expert_theta, gamma=self.gamma, epsilon = self.epsilon)		
		#print self.grids.rewards
		print "expert expected feature counts:"
		print exp_mu
	
		if safety is True:
			safety = 0.01
		prob = output_model(self.grids, starts, self.expert_policy, self.steps, unsafe, safety)
		print "model output finished ", prob
		mu_cex =  counterexample(self.grids, self.gamma, safety, epsilon)
		if mu_cex is not None:
			print mu_cex
		else:
			print "no counterexample found. comics says that it's safe!!!!!!!!!!!"
			

		file = open('log', 'a')
		for i in self.grids.feature_states:
			file.write(str(i))
		file.write("\n")
		#file.write(str(self.grids.loc_max_0))
		#file.write(str(self.grids.loc_max_1))
		#file.write(str(self.grids.loc_min_0))
		#file.write(str(self.grids.loc_min_1)+'\n')
		file.write(str(expert_theta) + '\n')
		file.write(str(exp_mu) + '\n')
		file.close()

		for prob in distribution:
			print prob, " optimal expert is teaching"
			for i in range(len(self.expert_policy)):
				for j in range(len(self.expert_policy[i])):
					if random.random() >= prob:
						actions = [0.0, 1.0, 2.0, 3.0, 4.0]
						random.shuffle(actions)
						if actions[0] == self.expert_policy[i, j]:
							self.demo_policy[i, j]=actions[1]
						else:
							self.demo_policy[i, j]=actions[0]
					else:
						self.demo_policy = self.expert_policy
		       	 				
			demo_mu = optimal_feature(self.grids, starts, self.steps, self.expert_policy, epsilon = self.epsilon, gamma=self.gamma)
			if safety is True:
				prob = output_model(self.grids, starts, self.expert_policy, self.steps, unsafe, safety)
				print "model output finished ", prob
				mu_cex =  counterexample(self.grids, self.gamma, safety, epsilon)
				if mu_cex is not None:
					print mu_cex
				else:
					print "no counterexample found. comics says that it's safe!!!!!!!!!!!"
				mu_g = np.sum(np.reshape(exp_u_g, [self.grids.y_max*self.grids.x_max, len(self.grids.features[-1][-1])]), 0)
                                file = open('log', 'a')
                                file.write("policy future reach unsafe state rate "+ str(prob) + "\n") 
                                file.close()      

				
			file = open('optimal_policy', 'w')
			for i in self.demo_policy:
				for j in i:
					file.write(str(j)+":")
				file.write("\n")
			file.close()


			file = open('log', 'a')
			file.write(str(prob) + " optimal expert is teaching\n")
			file.write(str(demo_mu) + " is the expected feature\n") 
			for i in self.demo_policy:
				for j in i:
					file.write(str(j)+":")
				file.write("\n")
			file.close()
			_, theta, policy, _= expert_train(self.grids, demo_mu, self.agent, starts = starts, steps= self.steps, epsilon= epsilon, iteration=self.iteration, gamma=self.gamma, start_theta= -1.0* expert_theta, MC = False, safety= None)

			unmatch = False
			for i in range(len(policy)):
				for j in range(len(policy[i])):
					if policy[i, j] != self.demo_policy[i, j]:
						print "feature matched policy is different with ", prob, " expert"
						file = open('log', 'a')

	  			  	        file.write("feature matched policy is different with " + str(prob) +" expert\n")
						
						file.write("learnt parameter " + str(theta)+'\n')
						for m in policy:
							for n in m:
								file.write(str(n)+":")
							file.write("\n")
						file.close()
						unmatch = True
						break
				if unmatch is True:
					break
				
			if unmatch is False:
				print "precisely learnt"
				file = open('log', 'a')
				file.write("learnt parameter " + str(theta)+'\n')
				file.write("policy precisely learnt\n")
				file.close()

			
		'''
		if safety is not None:
			safety = p_b_expert
		print "original expert policy's unsafe rate ", p_b_expert

		file = open('expert_policy', 'w')
		for i in self.expert_policy:
			for j in i:
				file.write(str(j)+":")
			file.write("\n")
		file.close()
		
		policy_temp = np.array(self.expert_policy)
		policy_temp[self.grids.loc_min_0[0]-1, self.grids.loc_min_0[1]-1] = 3
		policy_temp[self.grids.loc_min_0[0]-1, self.grids.loc_min_0[1]]=1
		policy_temp[self.grids.loc_min_0[0]-1, self.grids.loc_min_0[1]+1] = 1
		policy_temp[self.grids.loc_min_0[0], self.grids.loc_min_0[1]-1] = 2
		policy_temp[self.grids.loc_min_0[0], self.grids.loc_min_0[1]+1] = 1
		policy_temp[self.grids.loc_min_0[0]+1, self.grids.loc_min_0[1]-1] = 2
		print policy_temp
		mu_temp = optimal_feature(self.grids, starts, self.steps, policy_temp, epsilon = self.epsilon, gamma=self.gamma)
		print "hand-modified policy feature error", np.linalg.norm(exp_mu-mu_temp, ord=2)
		exp_u_g, p_g, exp_u_b, p_b = sample_feature(self.grids, self.agent, starts, self.steps, policy_temp, epochs= 5000, epsilon = self.epsilon, gamma=self.gamma)
		p_b_sum = np.sum(np.reshape(p_b, [self.grids.y_max*self.grids.x_max]))/(len(starts))
		print "new policy unsafe rate ", p_b_sum
			

		pylab.title('real reward. try real expert? type [y/n] in the terminal')
		draw_grids(self.grids.rewards, None)

		pylab.ion()
		pylab.title('rewards from expert train, close to continue')
		'''
		return self.expert_policy


		_, theta, policy, _= expert_train(self.grids, exp_mu, self.agent, starts = starts, steps= self.steps, epsilon= epsilon, iteration=self.iteration, gamma=self.gamma, start_theta= -1.0* expert_theta, MC = False, safety= None)
		for i in range(len(policy)):
			for j in range(len(policy[i])):
				if policy[i, j] != self.expert_policy[i, j]:
					print "feature matched policy is different with expert"
					'''
					exp_u_g, p_g, exp_u_b, p_b = sample_feature(self.grids, self.agent, starts, self.steps, policy, epochs= 5000, epsilon = self.epsilon, gamma=self.gamma)
					p_b_sum = np.sum(np.reshape(p_b, [self.grids.y_max*self.grids.x_max]))/(len(starts))
					print "feature matched policy unsafe rate ", p_b_sum						   '''
		return policy
	def MC_expert_train(self, starts = None, epochs = np.array([10000, 8000, 5000, 4000, 3000, 2000, 1000, 500, 100, 50, 10, 5]), unsafe = None, expert_theta = None, epsilon = None):
		
		if starts is None:
			starts = np.array(self.starts)
		if expert_theta is None:
			expert_theta = self.theta/np.linalg.norm(self.theta, ord=2)
		if epsilon is None:
			epsilon = self.epsilon

		self.expert_policy, exp_mu = real_optimal(self.grids, self.agent, starts = starts, steps = self.steps, theta = expert_theta, gamma = self.gamma, epsilon = self.epsilon)
		print "real optimal policy"
		print self.expert_policy
		print "real expected feature under optimal policy"
		print exp_mu
		demo_mu = exp_mu
		_, theta, learnt_policy,_ = expert_train(self.grids, demo_mu, self.agent, epsilon = epsilon, starts = starts, steps= self.steps, iteration = 10, gamma=self.gamma, start_theta = None, MC = False)
		self.grids.w_features(theta)
		learnt_mu, _ = optimal_feature(self.grids, starts, self.steps, learnt_policy, epsilon = self.epsilon, gamma=self.gamma)
		margin = np.linalg.norm(learnt_mu - demo_mu, ord = 2)
		prob = output_model(self.grids, starts, learnt_policy, self.steps, unsafe)
		print "Optimal policy unsafe probability ", prob
		file = open('log', 'a')
		file.write("MC expert train>>>>>Analytical demonstration prob" + str(prob) + " margin " + str(margin))
		file.close()

		for i_epoch in epochs:	
			exp_u_G, p_G, exp_u_B, p_B, _ = sample_feature(self.grids, self.agent, starts, self.steps, self.expert_policy, epochs= i_epoch, epsilon = self.epsilon , gamma=self.gamma, bounds = None, unsafe = unsafe)
			demo_mu = np.sum(np.reshape(exp_u_G, [self.grids.y_max*self.grids.x_max, len(self.grids.features[-1][-1])]) * np.reshape(p_G, [self.grids.y_max*self.grids.x_max, 1]) +   np.reshape(exp_u_B, [self.grids.y_max*self.grids.x_max, len(self.grids.features[-1][-1])]) * np.reshape(p_B, [self.grids.y_max*self.grids.x_max, 1]), 0) 
			_, theta, learnt_policy,_ = expert_train(self.grids, demo_mu, self.agent, epsilon = epsilon, starts = starts, steps= self.steps, iteration = 10, gamma=self.gamma, start_theta = None, MC = False)
			self.grids.w_features(theta)
			learnt_mu, _ = optimal_feature(self.grids, starts, self.steps, learnt_policy, epsilon = self.epsilon, gamma=self.gamma)
			margin = np.linalg.norm(learnt_mu - demo_mu, ord = 2)
			prob = output_model(self.grids, starts, learnt_policy, self.steps, unsafe)
			print "Optimal policy unsafe probability ", prob
			file = open('log', 'a')
			file.write("MC expert train>>>>>" + str(i_epoch) + " demonstrations prob" + str(prob) + " margin " + str(margin))
			file.close()
		
	def human_train(self, starts = None, expert_theta = None, epsilon= None):
		if starts is None:
			starts = np.array(self.starts)
		if expert_theta is None:
			expert_theta = self.theta/np.linalg.norm(self.theta, ord=2)
		if epsilon is None:
			epsilon = self.epsilon
		
		#file = open('demo_policy', 'w')
		#for i in starts:
		#	file.write(str(i[0])+","+str(i[1])+":")	
		#file.write("\n")				 
		#file.close()

		again = 'y'
		while(again != 'n' and again!= 'n'):
			if again != 'y' and again!= 'y':
				print "invalid input, exit...??"
				break
			else:
				start=starts[random.randint(0, len(starts)-1)]
				expert_temp, again = demo(self.grids, self.agent, start, steps= self.steps, gamma=self.gamma, epsilon= epsilon)
				self.expert.append(expert_temp)
		starts = []
		print "start training..."
			
		demo_mu = np.zeros(len(self.grids.features[-1][-1]))
		for i in range(len(self.expert)):
			demo_mu = demo_mu + self.expert[i]["mu"] 
			starts.append(self.expert[i]["trajectory"][0]["state"])
		demo_mu = demo_mu/len(self.expert)	
		print "expected demo mu is ", demo_mu

		_, theta, self.demo_policy,_ = expert_train(self.grids, demo_mu, self.agent, epsilon = epsilon, starts = starts, steps= self.steps, iteration = self.iteration, gamma=self.gamma, start_theta = None, MC = False)
		draw_grids(self.grids.rewards, None)
		file = open('log', 'a')	
		file.write("leanrt from human demo\n")
		for i in self.grids.feature_states:
			file.write(str(i))
		file.write("\n")
		#file.write(str(self.grids.loc_max_0))
                #file.write(str(self.grids.loc_max_1))
                #file.write(str(self.grids.loc_min_0))
                #file.write(str(self.grids.loc_min_1)+'\n')

		file.write("parameter "+ str(theta) + "\n")
		for i in self.demo_policy:
			for j in i:
				file.write(str(j)+":")
			file.write("\n")
		file.close()
		
		while True:
			real=raw_input("try modified policy? [y/n]")
			if real == 'y' or real == 'y':
				i = -2
				j = 0
				file = open('demo_policy', 'r')
				for line in file:
					if i == 0: 
						for j in range(len(line.split(":"))-1):
							self.demo_policy[i, j] = float(line.split(":")[j])
					i = i + 1			
				file.close()
				mu_temp = optimal_feature(self.grids, starts, self.steps, self.demo_policy, epsilon = self.epsilon, gamma=self.gamma)
				print "modified policy has feature error", np.linalg.norm(demo_mu-mu_temp, ord=2)

				_, theta, policy, _= expert_train(self.grids, mu_temp, self.agent, starts = starts, steps= self.steps, epsilon= epsilon, iteration=self.iteration, gamma=self.gamma, start_theta= None, MC = False, safety = None)
				for i in range(len(policy)):
					for j in range(len(policy[i])):
						if policy[i, j] != self.demo_policy[i, j]:
							print "and not so well learnt the modified policy"
							i = len(policy)
							break
				print "parameter learnt from modified policy is ", theta
			else:
				break

		return self.demo_policy



