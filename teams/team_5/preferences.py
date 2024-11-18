import numpy as np
import scipy.optimize as opt
import random
import math
from scipy.optimize import linear_sum_assignment
def phaseIpreferences(player, community, global_random):
    '''Return a list of task index and the partner id for the particular player. The output format should be a list of lists such that each element
    in the list has the first index task [index in the community.tasks list] and the second index as the partner id'''
    # list_choices = []
    # if player.energy < 0:
    #     return list_choices
    # num_members = len(community.members)
    # partner_id = num_members - player.id - 1
    # list_choices.append([0, partner_id])
    # if len(community.tasks) > 1:
    #     list_choices.append([1, partner_id])
    # list_choices.append([0, min(partner_id + 1, num_members - 1)])
    # return list_choices
    print("----------PHASE 1 BEGINS----------")
    community_size = len(community.members)
    task_size = len(community.tasks)
    ability_size = len(community.tasks[0])

    print(f"We have {community_size} community members.")
    print(f"We have {task_size} tasks to accomplish.")
    print(f"There are in total {ability_size} abilities.")

    list_choices = []

    for i in range(task_size):
        min_energy = np.inf
        best_partner_id = -1 
        print(f"THIS IS TASK {i}")
        for j in range(community_size):
            if community.members[j].id == player.id:
                print(f"FOUND MYSELF, I AM PLAYER {player.id}")
                continue
            energy_expended = sum([max(community.tasks[i][l] - max(community.members[j].abilities[l], player.abilities[l]), 0) for l in range( ability_size)])
            if energy_expended < min_energy:
                min_energy = energy_expended
                best_partner_id = j
        list_choices.append([i, best_partner_id])
        print(f"TASK {i} BEST PARTNER IS {best_partner_id}")

    return list_choices
            
    # num_values = len(V)
    
    # cost_matrix = np.zeros((size, size))
    # num_of_abilities = len(community.members[0].abilities)
    # # Fill the cost matrix with relative differences
    # for o in range(len(community.tasks)):
    #     for i in range(size):
    #         for j in range(size):
    #             energy_expended = (sum(max(community.tasks[o] - (max(community.members[i].abilities[l], community.members[j].abilities[l])), 0) for l in range(num_of_abilities)))
    #             cost_matrix[i][j] = energy_expended
    #     row_indices, col_indices = linear_sum_assignment(cost_matrix)
    #     print(f"BEST MEMBER PAIR FOR TASK {o} IS {(row_indices, col_indices)}")
            

    # Solving the assignment problem

def phaseIIpreferences(player, community, global_random):
    '''Return a list of tasks for the particular player to do individually'''
    bids = []
    if player.energy < 0:
        return bids
    num_abilities = len(player.abilities)
    for i, task in enumerate(community.tasks):
        energy_cost = sum([max(task[j] - player.abilities[j], 0) for j in range(num_abilities)])
        if energy_cost > 0:
            continue
        bids.append(i)
    return bids
