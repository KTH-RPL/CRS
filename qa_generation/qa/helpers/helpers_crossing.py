import random 
from collections import Counter


def counter_sig(cntr: Counter):
    return tuple(sorted((str(k).strip().lower(), int(v)) for k, v in cntr.items() if int(v) > 0))

def format_type_answer_sentence(count: int) -> str:
    """Answer sentence for crossing-count questions, e.g. "There are 2 crossings."."""
    return f"There are {count} crossings."

def make_decoy_sentences_crossing(
        true_counts: Counter,
        nodes,
        G,
        global_types,
        key,
        k=3,
        p_delete=0.25,
        p_add=0.25,
        p_change=0.25,
        p_mixed=0.25,
        rng=None, 
    ):
    """
    Produce up to k decoy sentences (strings). Strategy probabilities control how
    often each strategy is attempted; the function keeps trying different candidate
    transformations until k unique decoys are created or a limit of attempts is hit.
    """
    if rng is None:
        rng = random.Random(random.getrandbits(64))

    true_total = sum(true_counts.values())
    true_sentence = format_type_answer_sentence(true_total)

    strategies = []
    if p_delete > 0:
        strategies.append(("delete", p_delete, _apply_delete))
    if p_add > 0:
        strategies.append(("add", p_add, _apply_add_unique))
    if p_change > 0:
        strategies.append(("change", p_change, _apply_change_unique))
    if p_mixed > 0:
        strategies.append(("mixed", p_mixed, _apply_mixed_unique))

    total_p = sum(p for _, p, _ in strategies)
    if total_p <= 0:
        strategies = [("change", 1.0, _apply_change_unique)]
        total_p = 1.0
    weights = [p / total_p for _, p, _ in strategies]

    candidates = []
    structured_candidates = []
    seen = set([true_sentence])
    seen_sigs = {counter_sig(true_counts)}
    attempts = 0
    max_attempts = 8

    while len(candidates) < k and attempts < max_attempts:
        attempts += 1
        _, _, op = rng.choices(strategies, weights, k=1)[0]
     

        modified = op(true_counts, nodes, G, global_types, rng, key)

        if modified is None:
            continue

        clean = Counter({str(t).strip().lower(): int(v) for t, v in modified.items() if int(v) > 0})
        tot = sum(clean.values())
        
        cand_sentence = format_type_answer_sentence(tot)
        clean_sig = counter_sig(clean)
        if cand_sentence not in seen and clean_sig not in seen_sigs:
            seen.add(cand_sentence)
            seen_sigs.add(clean_sig)
            candidates.append(cand_sentence)
            structured_candidates.append({"text":cand_sentence, "counts": clean})

    if len(candidates) < k and true_counts:
        dom = max(true_counts, key=lambda t: true_counts[t])
        for d in (-2, -1):
            tmp = true_counts.copy()
            tmp[dom] = max(0, tmp[dom] + d)
            if tmp[dom] == 0:
                del tmp[dom]
            s = format_type_answer_sentence(sum(tmp.values()))
            if s not in seen:
                seen.add(s)
                candidates.append(s)
                structured_candidates.append({"text":s, "counts": tmp})
            if len(candidates) >= k:
                break

    if len(candidates) < k and sum(true_counts.values()) != 0:
        zero = format_type_answer_sentence(0)
        if zero not in seen:
            candidates.append(zero)
            structured_candidates.append({"text":zero, "counts": Counter()})

    rng.shuffle(structured_candidates)
    return structured_candidates[:k]

def _apply_delete(cntr: Counter, nodes, G, global_types, rng, key):
    """Delete a single lane (remove one count from its type)."""
    if not nodes:
        return None
    node = rng.choice(nodes)
    props = G.nodes[node].get("properties") or {}
    t = props.get(key)
    new = cntr.copy()
    new[t] = max(0, new[t] - 1)
    if new[t] == 0:
        del new[t]
    return new

    
def _apply_add_unique(cntr: Counter, nodes, G, global_types, rng, key):
    """
    Add one lane, but only pick a type that is NOT already present in cntr,
    choosing from global_types when available. If no new type available, return None.
    """
    new = cntr.copy()
    if global_types:
        candidates = [t for t in global_types if new.get(t, 0) == 0]
        if not candidates:
            return None
        t = rng.choice(candidates)
    else:
        t = "vehicle"
    new[t] = new.get(t, 0) + 1
    return new


def _apply_change_unique(cntr: Counter, nodes, G, global_types, rng, key):
    """
    Change the type of one matched node: move 1 from old type to a new type
    selected from global_types, but only if that new_type is not already present
    (so uniqueness is preserved). If no valid target type exists, return None.
    """
    if not nodes:
        return None
    node = rng.choice(nodes)
    props = G.nodes[node].get("properties") or {}
    old = props.get(key)

    choices = [t for t in (global_types or []) if t != old and cntr.get(t, 0) == 0]
    if not choices:
        return None

    new_type = rng.choice(choices)
    new = cntr.copy()
    if old in new:
        new[old] -= 1
        if new[old] <= 0:
            del new[old]
    new[new_type] = new.get(new_type, 0) + 1
    return new


def _apply_mixed_unique(cntr: Counter, nodes, G, global_types, rng, key):
    """
    Compose unique add + unique change (or vice-versa). If either sub-op can't
    run (returns None), try to use the other op in isolation. Return None if neither works.
    """
    first = _apply_add_unique(cntr, nodes, G, global_types, rng, key)
    if first is None:
        second = _apply_change_unique(cntr, nodes, G, global_types, rng, key)
        return second
    second = _apply_change_unique(first, nodes, G, global_types, rng, key)
    if second is None:
        return first
    return second