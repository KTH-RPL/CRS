import random 
import re

from qa.helpers.definitions import VERBOSE_LANES


def format_type_answer_sentence(count, phrase, type_counts, normalize_lane) -> str:
    """
    Desired style:
      - "There are 2 lanes leaving to the right, all standard travel lanes."
      - "There are 3 lanes leaving to the right: 2 standard travel lanes and 1 bus lane."
    """
    if count == 0:
        if phrase not in ["in total", "main_road"]:
            return f"There are no lanes {phrase}."
        else:
            return "There are no lanes."
            
    if len(type_counts) == 1:
        only_type = next(iter(type_counts.keys()))
        if phrase == "main_road":
            only_type += "_main_road"
        type_phrase = normalize_lane(only_type)  
        if count != 1: type_phrase = re.sub(r"\blane\b", "lanes", type_phrase) 
        if phrase not in ["in total", "main_road"]:
            if count == 1:
                return f"There is just {count} {type_phrase} {phrase}."
            if random.random() > 0.5:
                return f"There are {count} lanes {phrase}, all {type_phrase}."
            else:
                return f"There are {count} {type_phrase} {phrase}."
        else:
            if count == 1:
                return f"There is just {count} {type_phrase}."
            return f"There are {count} {type_phrase}."
            

    parts = []
    for t, c in sorted(type_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if phrase == "main_road":
            t += "_main_road"
        base = normalize_lane(t)

        if c > 1:
            base = re.sub(r"\blane\b", "lanes", base)
        parts.append(f"{c} {base}")

    if len(parts) == 2:
        comp = f"{parts[0]} and {parts[1]}"
    else:
        comp = ", ".join(parts[:-1]) + ", and " + parts[-1]

    return f"There are {comp}."


    


def build_lane_type_evidence(correct_val):
    return f"The lane is a {VERBOSE_LANES[correct_val]}."


def _make_decoy_sets(correct_set, wrong_pool, k=10):
    """
    Return k decoy lane-id sets using:
      - remove
      - add
      - mixed
    Ensures they differ from correct_set and from each other.
    """
    correct_set = set(correct_set)
    wrong_pool = list(set(wrong_pool) - correct_set)

    decoys = []
    attempts = 0

    if not correct_set and not wrong_pool:
        return []

    while len(decoys) < k and attempts < 50:
        attempts += 1

        mode = random.choice(["remove", "add", "mixed"])

        cand = set(correct_set)

        if mode == "remove":
            if len(cand) == 0:
                continue
            rmax = len(cand) if len(cand) == 1 else len(cand) - 1
            n_remove = random.randint(1, rmax)
            cand -= set(random.sample(list(cand), n_remove))

        elif mode == "add":
            if not wrong_pool:
                continue
            n_add = random.randint(1, min(2, len(wrong_pool)))
            cand |= set(random.sample(wrong_pool, n_add))

        else:
            if len(cand) > 0:
                rmax = len(cand) if len(cand) == 1 else len(cand) - 1
                n_remove = random.randint(1, rmax)
                cand -= set(random.sample(list(cand), n_remove))
            if wrong_pool:
                n_add = random.randint(1, min(2, len(wrong_pool)))
                cand |= set(random.sample(wrong_pool, n_add))
            else:
                pass

        if cand == correct_set:
            continue
        if cand in decoys:
            continue

        decoys.append(cand)

    return decoys

