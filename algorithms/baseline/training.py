import sys
sys.path.insert(0, '/Users/shatianwang/Desktop/Elevator-MARL-Environment')
import environment as gym
import random
import time
import logging
from Q_learning_ext.nnet import NNet
import tensorflow as tf
import numpy as np

logger = gym.logger.get_my_logger(__name__)

def timed_function(func):
    def decorated_func(*args, **kwargs):
        s = time.time()
        output = func(*args, **kwargs)
        e = time.time()
        logger.info("{} finished in {} seconds".format(func.__name__,e-s))
        return output
    return decorated_func

if __name__=="__main__":
    logging.disable(logging.INFO)
    nElevator = 1
    nFloor = 10
    spawnRates = [1/360]+[1/360]*(nFloor-1)
    avgWeight = 135
    weightLimit = 1200
    loadTime = 1
    simulation_hours = 950 # number of simulation hours to run
    beta = 0.01 # exponential decay factor for target computation
    lr = 1e-4 # NNet learning rate
    factor = 0.992 # specific for Q-learning-ext, controls exploration behavior


# Initialization
# initialize environment
env = gym.make(nElevator, nFloor, spawnRates, avgWeight, weightLimit, loadTime)
obssize = env.observation_space_size
actsize = env.action_space_size
print("obssize", obssize)
print("actsize", actsize)


# initialize tensorflow session
sess = tf.Session()

# initialize optimizer
optimizer = tf.train.AdamOptimizer(lr)

# initialize a NNet for each elevator
Q=[]
for i in range(nElevator):
    with tf.variable_scope("Q"+str(i)):
        Q.append(NNet(obssize, actsize, sess, optimizer))

# if resume training using prev trained model
# Use the saver to restore trained model from disk
# ckpt_path = "./2E_8F/2E_8F_q_learning_ext_model.ckpt" # specify path to the checkpoint file
# saver = tf.train.Saver()
# saver.restore(sess, ckpt_path)
# print("Model restored.")
## ---------------------------------------------------
# if train from scratch, switch to the code below
sess.run(tf.global_variables_initializer())
ckpt_path = "./1E_10F/1E_10F_q_learning_ext_model.ckpt" # specify path to the checkpoint file for model storage
## ---------------------------------------------------


# Training
env_state_dict = env.reset()
ss = env_state_dict["states"] # a list of states, one state for each decision agent

# lists that store the most recent decision state and performed action of each agent
prev_actions = np.full(nElevator, None)
prev_states = np.full(nElevator, None)

# main iteration of training
# env.now() gives the total elapsed simulation time in seconds
last_checkpoint_time = 0
print_counter = 0
while env.now() <= simulation_hours * 3600:
    # save updated graph after every 10 hours of training
    # remember temperature matters; so cannot train in segments
    if env.now() - last_checkpoint_time > 10 * 3600:
        tf.train.Saver().save(sess, ckpt_path)
        print("graph saved after ", round(env.now()/3600, 1), "simulation hours")
        last_checkpoint_time = env.now() # set last_checkpoint_time to current time

        # # reset environment every 10 hours
        # env = gym.make(nElevator, nFloor, spawnRates, avgWeight, weightLimit, loadTime)
        # env_state_dict = env.reset()
        # ss = env_state_dict["states"] # a list of states, one state for each decision agent



    decision_agents = env_state_dict["decision agents"]
    R = env_state_dict["rewards"]
    actions = []
    print_counter += 1
    # each decision agent updates NNet and selects action
    for i in range(len(decision_agents)):
        agent = decision_agents[i]

        # construct legal_actions_list, in ascending order of action index
        legal_actions_list = list(env.legal_actions(agent))
        legal_actions_list.sort()
        # construct a boolean representation of legal_actions
        legal_actions_bool = np.full(actsize, False)
        for action in env.legal_actions(agent):
            legal_actions_bool[action] = True
        # compute q-values
        q_vals = Q[agent].compute_Qvalues([ss[i]])[0]
        loss = None

        # Update NNet
        if prev_actions[agent] != None: # if not the first time being a decision agent
            # update corresponding NNet
            time_elapsed = ss[i][-1]
            # compute min Q value in current state
            min_Q_val = np.amin(q_vals[legal_actions_list])
            # compute target Q value of PREVIOUS state, action pair
            target = R[i] + np.exp(-beta * time_elapsed) * min_Q_val
            # update agent's NNet parameters
            loss, _ = Q[agent].train([prev_states[agent]], [prev_actions[agent]], [target])

        # Choose action
        # compute temperature used in softmax action distribution
        T = 2.0 * (factor ** (round(env.now()/3600,4)))
        # compute a probability distribution on legal actions
        # len(prob_dist) = len(legal_actions)
        # in ascending order of legal actions' indices
        prob_dist, _ = Q[agent].compute_legal_action_prob_dist([ss[i]], legal_actions_bool, T)

        # sample a legal action from prob_dist of legal actions
        action = np.random.choice(legal_actions_list, p = prob_dist)

        # update prev_actions and prev_states lists
        prev_actions[agent] = action
        prev_states[agent] = ss[i]
        actions.append(action)

        if print_counter % 50 in [0, 1, 2, 3, 4]:
            if print_counter % 50 == 0:
                print("----------------------------------------")
            print("action probability distribution", prob_dist)
            print("legal Q_vals: ", q_vals[legal_actions_list])
            print("reward: ",R[i])
            print("loss: ", loss)
            print("temperature: ", T)
            print("requested calls from within: ", ss[i][-11:-1])

    env_state_dict = timed_function(env.step)(actions)
    ss = env_state_dict["states"]

    ## uncomment to enable visualization
    if print_counter % 50 in [0, 1, 2, 3, 4]:
        env.render()
        if print_counter % 50 == 4:
            print("----------------------------------------")

# save the final model
tf.train.Saver().save(sess, ckpt_path)
