import json
import os

FILE_NAME = "data/experiment_results.json"


def load_results():
    if not os.path.exists(FILE_NAME):
        return []

    with open(FILE_NAME, "r") as file:
        return json.load(file)


def record_trial(scenario, expected, predicted):
    results = load_results()

    results.append({
        "Scenario": scenario,
        "Expected": expected,
        "Predicted": predicted,
        "Correct": expected == predicted
    })

    os.makedirs("data", exist_ok=True)

    with open(FILE_NAME, "w") as file:
        json.dump(results, file, indent=4)


def calculate_accuracy():
    results = load_results()

    total = len(results)

    if total == 0:
        return 0, 0, 0, 0.0

    correct = sum(1 for result in results if result["Correct"])
    incorrect = total - correct

    accuracy = (correct / total) * 100

    return total, correct, incorrect, accuracy


def get_results():
    return load_results()