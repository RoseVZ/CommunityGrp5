import numpy as np
import scipy.optimize as opt
import random
import math
from scipy.optimize import linear_sum_assignment

# List of things to implement (Feel free to add to it)
#TODO: Finding the weakest players (Dummy players only? Or we include weak players too)
#TODO: Determine when a player should rest
#TODO: Minimize the number of pairs a player volunteers for (Currently we are volunteering for a lot)

def phaseIpreferences(player, community, global_random):
    '''Return a list of task index and the partner id for the particular player. The output format should be a list of lists such that each element
    in the list has the first index task [index in the community.tasks list] and the second index as the partner id'''

    exhausted = True if player.energy < 0 else False 
    list_choices = []

    # If player is exhausted, return an empty list (no tasks)
    if player.energy < 0:
        return list_choices

    # Check if the player can do individual tasks (no partner needed)
    for i, task in enumerate(community.tasks):
        energy_cost = sum([max(task[j] - player.abilities[j], 0) for j in range(len(player.abilities))])
        if energy_cost == 0:
           # print("Can take individual Task: ", task, " Player: ", player.abilities)
            return list_choices

    # Prioritize tasks based on energy cost and reward-to-energy ratio (score)
    task_priorities = []

    for i, task in enumerate(community.tasks):
        energy_cost = sum([max(task[j] - player.abilities[j], 0) for j in range(len(player.abilities))])
        reward = sum([task[j] for j in range(len(task))])  # Sum of task difficulty (can be adjusted)
        score = reward / (energy_cost + 1)  # Reward-to-energy ratio (higher is better)
        task_priorities.append((i, score, energy_cost))

    # Sort tasks by score (reward-to-energy ratio, descending)
    task_priorities.sort(key=lambda x: x[1], reverse=True)

    # Dynamic adjustment of max tasks to consider
    max_tasks_to_consider = int(player.energy) # Adjust based on player’s energy (higher energy allows more tasks)

    top_tasks = task_priorities[:max_tasks_to_consider]

    exhausted_penalty = 0.5 

    # Find partners for the selected tasks based on combined abilities and energy constraints
    for task_id, score, _ in top_tasks:
        best_partner = None
        min_cost = float('inf')

        # Iterate through community members to find the best partner
        for partner in community.members:
            if partner.id == player.id:
                continue

            combined_abilities = [player.abilities[j] + partner.abilities[j] for j in range(len(player.abilities))]
            energy_cost = sum([max(community.tasks[task_id][j] - combined_abilities[j], 0) for j in range(len(player.abilities))])
            added_cost = exhausted_penalty if partner.energy < 0 else 0

            # Total energy cost considering player and partner's combined abilities
            comparison_metric = energy_cost + added_cost

            if comparison_metric < min_cost and (partner.energy - energy_cost) > -10 and (player.energy - energy_cost) > -10:
                min_cost = comparison_metric
                best_partner = partner.id

        # If a compatible partner is found, assign the task to the player and partner
        if best_partner is not None:
            list_choices.append([task_id, best_partner])

    return list_choices
       
def phaseIIpreferences(player, community, global_random):
    '''Return a list of tasks for the particular player to do individually'''
    bids = []
    # if player.energy < 0:
    #     return bids
    
    num_abilities = len(player.abilities)
    spent_energy = 0
    # task_scores = []

    for i, task in enumerate(community.tasks):
        energy_cost = sum([max(task[j] - player.abilities[j], 0) for j in range(num_abilities)])

        if energy_cost <= 0: #If it doesn't cost energy, do it.
            bids.append(i)
            continue
        
      
        if player.energy - (energy_cost + spent_energy) > -10: #If I am alive, I am gonna work.
            spent_energy += energy_cost
            bids.append(i)
            continue

        # Tasks with higher unmet abilities and lower energy cost are prioritized
        # benefit = sum(task) - energy_cost
        # if energy_cost <= player.energy:  # Only considering tasks within energy limits
            # task_scores.append((i, benefit / (energy_cost + 1)))

    # Sorting by benefit-to-energy ratio and returning top tasks
    # task_scores.sort(key=lambda x: -x[1])
    # bids = [task_id for task_id, _ in task_scores[:10]]  # Bidding for top 10 tasks
    return bids
