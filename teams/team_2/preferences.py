import numpy as np
from scipy.optimize import linear_sum_assignment
import traceback
import sys

import torch
import torch.nn as nn
import torch.nn.functional as F

# check if we're running a train simulation
# or running for real
training = False
for args in sys.argv:
    if args == "train=true":
        training = True
        break


class TaskScorerNN(nn.Module):
    def __init__(self, task_feature_size, player_state_size, hidden_size):
        super(TaskScorerNN, self).__init__()
        self.fc1 = nn.Linear(task_feature_size + player_state_size, hidden_size)
        self.fc2 = nn.Linear(hidden_size, hidden_size)
        self.fc3 = nn.Linear(hidden_size, 1)  # Outputs a single score for a task

    def forward(self, task_features, player_state):
        # Concatenate task features and player state
        combined = torch.cat(
            [
                task_features if task_features.ndim > 1 else task_features.view(-1),
                player_state,
            ],
            dim=-1,
        )
        x = F.relu(self.fc1(combined))
        x = F.relu(self.fc2(x))
        score = self.fc3(x)  # Outputs score
        return score


class RestDecisionNN(nn.Module):
    def __init__(self, input_size, hidden_size):
        super(RestDecisionNN, self).__init__()
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.fc2 = nn.Linear(hidden_size, 1)  # Single output for rest score

    def forward(self, features):
        x = F.relu(self.fc1(features))
        score = self.fc2(x)
        return score


def decide_action(
    task_features, player_state, task_scorer, rest_decider, k, max_tasks=100
):
    """
    Decides whether to perform a task or rest.

    Args:
        task_features (list): List of features for each task.
        player_state (object): Current state of the player.
        task_scorer (nn.Module): Neural network scoring tasks.
        rest_decider (nn.Module): Neural network deciding rest.
        k (int): Number of top tasks to consider.
        max_tasks (int): Maximum number of tasks the model can handle.

    Returns:
        action (int): 0 to len(task_features)-1 for tasks, len(task_features) for rest.
    """
    player_state_tensor = torch.tensor(player_state, dtype=torch.float32)

    task_vectors = [torch.tensor(task, dtype=torch.float32) for task in task_features]

    task_scores = torch.tensor(
        [task_scorer(task_vector, player_state_tensor) for task_vector in task_vectors]
    )

    # Pad task scores to max_tasks with 0 if fewer tasks are available
    if len(task_scores) <= max_tasks:
        # 1 for rest
        padding = torch.zeros(max_tasks - len(task_scores) + 1)
        task_scores = torch.cat([task_scores, padding])

    # Select top k scores (valid tasks only)
    num_available_tasks = len(task_features)
    top_k_scores, top_k_indices = torch.topk(
        task_scores[:num_available_tasks], min(k, num_available_tasks)
    )

    # Aggregate features for rest decision
    rest_input = torch.cat(
        [
            torch.mean(top_k_scores).unsqueeze(0),  # Mean score of top k tasks
            torch.tensor(player_state),  # Add player and community features
        ]
    )

    # Score rest action
    rest_score = rest_decider(rest_input).item()

    # Combine task scores and rest score
    combined_scores = task_scores.clone()
    combined_scores[max_tasks] = rest_score  # Append rest score after valid tasks
    num_available_tasks = task_scores.size(0)

    # Find the action with the highest score
    action = torch.argmax(combined_scores).item()

    # If rest is chosen, return []
    if action == max_tasks:
        return []
    # Exclude rest and pick the argmax among the top k tasks
    top_k_scores, top_k_indices = torch.topk(task_scores, k=k)
    # Making sure we dont select any tasks already done
    return [i for i in top_k_indices.tolist() if i < len(task_vectors)]


def count_tired_exhausted(community):
    tired = len([m for m in community.members if -10 < m.energy < 0])
    exh = len([m for m in community.members if -10 > m.energy])
    return tired, exh


def rest_energy_gain(energy):
    if abs(energy) == 10:
        return 0
    if energy < 0:
        return 0.5
    return 1


def create_cost_matrix(player, community):
    cost_matrix = []
    for task in community.tasks:
        task_costs = []
        for member in community.members:
            # Compute the element-wise maximum of abilities
            max_abilities = [
                max(i, j) if member.energy >= 0 else float("inf")
                for i, j in zip(player.abilities, member.abilities)
            ]
            # Compute the delta and absolute values
            delta = [abs(max_val - req) for max_val, req in zip(max_abilities, task)]
            # Total cost is the sum of deltas
            total_cost = sum(delta)
            task_costs.append(total_cost)
        cost_matrix.append(task_costs)
    cost_matrix = np.array(cost_matrix)
    return cost_matrix


def create_cost_matrix_raw(community):
    cost_matrix = []
    for task in community.tasks:
        task_costs = []
        for member in community.members:
            # Compute the delta and absolute values
            delta = [max(val - req, 0) for val, req in zip(member.abilities, task)]
            # Total cost is the sum of deltas
            total_cost = sum(delta)
            if member.energy <= -10:
                total_cost = float("inf")
            task_costs.append(total_cost)
        cost_matrix.append(task_costs)
    cost_matrix = np.array(cost_matrix)
    return cost_matrix


def create_cost_matrix_would_exhaust(community):
    cost_matrix = []
    for task in community.tasks:
        task_costs = []
        for member in community.members:
            # Compute the delta and absolute values
            delta = [max(val - req, 0) for val, req in zip(member.abilities, task)]
            # Total cost is the sum of deltas
            total_cost = sum(delta)
            if member.energy - total_cost <= -10:
                total_cost = float("inf")
            task_costs.append(total_cost)
        cost_matrix.append(task_costs)
    cost_matrix = np.array(cost_matrix)
    return cost_matrix


def create_cost_matrix_would_tire(community):
    cost_matrix = []
    for task in community.tasks:
        task_costs = []
        for member in community.members:
            # Compute the delta and absolute values
            delta = [max(val - req, 0) for val, req in zip(member.abilities, task)]
            # Total cost is the sum of deltas
            total_cost = sum(delta)
            if member.energy - total_cost < 0:
                total_cost = float("inf")
            task_costs.append(total_cost)
        cost_matrix.append(task_costs)
    cost_matrix = np.array(cost_matrix)
    return cost_matrix


def count_lower_cost_players(player_cost_array, cost_matrix):
    """
    Count the number of players with lower costs than the given player for each task.

    Args:
        player_cost_array (np.ndarray): 1D array of the player's costs for each task.
        cost_matrix (np.ndarray): 2D array of shape (num_tasks, num_members), where each entry is the cost for a member to perform a task.

    Returns:
        list: A list where each element is the count of players with lower costs for the corresponding task.
    """
    # Ensure the player's cost array is an array
    player_cost_array = np.array(player_cost_array)

    # Compare the player's costs with all members' costs for each task
    lower_cost_counts = np.sum(cost_matrix < player_cost_array[:, None], axis=1)

    return lower_cost_counts.tolist()


def best_partner(task: np.ndarray):
    for partner_id in range(len(task)):
        if task[partner_id] == task.min():
            return partner_id

    raise Exception("All arrays have a minimum value")


def create_tasks_feature_vector(player, community):

    player_cost_array = []

    num_abilities = len(player.abilities)
    for i, task in enumerate(community.tasks):
        energy_cost = sum(
            [max(task[j] - player.abilities[j], 0) for j in range(num_abilities)]
        )
        # if player.energy - energy_cost >= 0:
        player_cost_array.append(energy_cost)

    mat_raw = create_cost_matrix_raw(community)
    mat_tire = create_cost_matrix_would_tire(community)
    mat_exhaust = create_cost_matrix_would_exhaust(community)

    tasks_lower_raw = count_lower_cost_players(player_cost_array, mat_raw)
    tasks_lower_tire = count_lower_cost_players(player_cost_array, mat_tire)
    tasks_lower_exhaust = count_lower_cost_players(player_cost_array, mat_exhaust)

    task_costs = []
    for i, task in enumerate(community.tasks):
        subvector = []
        task_difficulty = sum(task) / len(task)
        subvector.append(task_difficulty)
        subvector.append(player_cost_array[i])
        subvector.append(tasks_lower_raw[i] / len(community.members))
        subvector.append(tasks_lower_tire[i] / len(community.members))
        subvector.append(tasks_lower_exhaust[i] / len(community.members))

        task_costs.append(subvector)
    task_costs = np.array(task_costs)
    return task_costs


def phaseIpreferences(player, community, global_random):
    """Return a list of task index and the partner id for the particular player. The output format should be a list of lists such that each element
    in the list has the first index task [index in the community.tasks list] and the second index as the partner id
    """
    # if we're training (phase 2), we don't want to do any pairing
    if training:
        return []

    list_choices = []
    if player.energy < 0:
        return list_choices

    cost_matrix = create_cost_matrix(player, community)

    best_partner_for_task = [
        (task_id, best_partner(cost_matrix[task_id]), cost_matrix[task_id].min())
        for task_id in range(len(cost_matrix))
    ]
    best_partner_for_task.sort(key=lambda x: x[2])

    requested_partners = []

    # to incentivize players to not request pairing up with the best member in the community,
    # we require that they at least request 5 different partners
    PARTNER_REQUEST_AMOUNT = 5
    potential_partners = set()
    curr_idx = 0
    while len(potential_partners) < PARTNER_REQUEST_AMOUNT and curr_idx < len(
        best_partner_for_task
    ):
        task_id, partner_id, cost = best_partner_for_task[curr_idx]
        if partner_id not in potential_partners:
            requested_partners.append([task_id, partner_id])
            potential_partners.add(partner_id)

        curr_idx += 1

    return requested_partners


def phaseIIpreferences(player, community, global_random):
    """Return a list of tasks for the particular player to do individually"""
    try:

        # NN part
        # Initialize

        # Hardcoded as 1, to be only the cost of the task - this can be changed.
        task_feature_size = 5
        player_params_size = 9
        hidden_size = 64

        if not hasattr(player, "turn"):
            prefix = "teams/team_2/"
            for arg in sys.argv:
                if arg.startswith("prefix="):
                    prefix = "models/" + arg[len("prefix=") :] + "_"
                    break

            player.taskNN = TaskScorerNN(
                task_feature_size=task_feature_size,
                player_state_size=player_params_size,
                hidden_size=hidden_size,
            )
            player.taskNN.load_state_dict(
                torch.load(prefix + "task_weights.pth", weights_only=True)
            )
            player.restNN = RestDecisionNN(
                # The 1 here is hardcoded because we get a mean of the task scores
                input_size=player_params_size + 1,
                hidden_size=hidden_size,
            )
            player.restNN.load_state_dict(
                torch.load(prefix + "rest_weights.pth", weights_only=True)
            )

            player.turn = 1
            player.num_tasks = len(community.members) * 2
            # This should contain the params for decision, such as player.energy, etc
            player.params = [
                len(community.members),
                len(community.tasks),
                len(community.members) / (len(community.tasks) + 1),
                player.turn,
                player.energy,
                min(player.energy, 0) ** 2,
                0,  # Energy to gain from resting
                0,  # Num tired
                0,  # Num exhausted
            ]
        else:
            player.turn += 1
            tired, exh = count_tired_exhausted(community)
            player.params = [
                len(community.members),
                len(community.tasks),
                len(community.members) / (len(community.tasks) + 1),
                player.turn,
                player.energy,
                min(player.energy, 0) ** 2,
                rest_energy_gain(player.energy),
                tired,
                exh,
            ]

        task_features = create_tasks_feature_vector(player, community)
        action = decide_action(
            task_features,
            player.params,
            player.taskNN,
            player.restNN,
            k=min(3, len(community.tasks)),
            max_tasks=player.num_tasks,
        )
        return action
    except Exception as e:
        print(f"CRASH: {e}")
        traceback.print_exc()
