# engine.py
import random
from copy import deepcopy
from characters import (
    Character, create_all_character_prototypes,
    rw_attack, ea_attack, tb_attack, ca_attack, qk_attack,
    rw_heroic_raise, rw_ruby_shield, ea_arrow_shower, ea_sharp_aim,
    tb_shiny_flex, tb_stun_punch, ca_vital_stab, ca_sneak_boost,
    qk_die_for_me, qk_kings_command, diceroll, clamp
)

# Clone function using deepcopy
def clone_character(proto):
    return deepcopy(proto)

def is_status_move(name):
    if name is None: return False
    return name not in ("attack",)

class BattleEngine:
    def __init__(self, player_protos, cpu_protos):
        # player_protos and cpu_protos are lists of character prototypes (to be cloned)
        self.player_prototypes = player_protos
        self.cpu_prototypes = cpu_protos

        # selected teams (filled when start_battle called)
        self.player_team = []
        self.cpu_team = []

        # heal uses
        self.player_heal_left = 3
        self.cpu_heal_left = 3

        # action placeholders (list of tuples per character index)
        self.player_actions = []   # each entry: ("attack"/"heroic_raise"/..., param)
        self.cpu_actions = []

        # logs
        self.log = []
        self.round_number = 0

        # randomness seed left default

    def start_battle(self, player_indices, cpu_indices=None):
        # player_indices: indices into self.player_prototypes to pick (3)
        self.player_team = [clone_character(self.player_prototypes[i]) for i in player_indices]
        # if cpu_indices passed, use them; else pick random 3 from cpu_prototypes
        if cpu_indices is None:
            choices = list(range(len(self.cpu_prototypes)))
            cpu_indices = random.sample(choices, 3)
        self.cpu_team = [clone_character(self.cpu_prototypes[i]) for i in cpu_indices]

        # reset uses, logs, round
        self.player_heal_left = 3
        self.cpu_heal_left = 3
        self.player_actions = [None] * len(self.player_team)
        self.cpu_actions = [None] * len(self.cpu_team)
        self.log = []
        self.round_number = 1

    # Utility helpers
    def all_dead(self, team):
        return all(not c.is_alive() for c in team)

    def _choose_cpu_actions(self):
        # ported CPU AI from earlier simulator (obeys status-repeat)
        actions = [None] * len(self.cpu_team)
        cpu_heal_left = self.cpu_heal_left

        for idx, actor in enumerate(self.cpu_team):
            if not actor.is_alive():
                actions[idx] = ("none", None)
                continue
            attempt = 0
            chosen = None
            while True:
                attempt += 1
                if cpu_heal_left > 0:
                    # heal if someone low
                    low_ally = min([a for a in self.cpu_team if a.is_alive()], key=lambda x: x.hp, default=None)
                    if low_ally and low_ally.hp < low_ally.max_hp * 0.35:
                        chosen = ("heal_single", self.cpu_team.index(low_ally))
                    else:
                        if actor.shortname == "EA":
                            r = random.random()
                            if r < 0.25:
                                chosen = ("arrow_shower", None)
                            elif r < 0.45:
                                chosen = ("sharp_aim", None)
                            else:
                                targets = [i for i,p in enumerate(self.player_team) if p.is_alive()]
                                chosen = ("attack", random.choice(targets)) if targets else ("none", None)
                        elif actor.shortname == "TB":
                            targets = [i for i,p in enumerate(self.player_team) if p.is_alive() and not p.stunned]
                            if targets and random.random() < 0.25:
                                chosen = ("stun_punch", random.choice(targets))
                            else:
                                targets = [i for i,p in enumerate(self.player_team) if p.is_alive()]
                                chosen = ("attack", random.choice(targets)) if targets else ("none", None)
                        elif actor.shortname == "RW":
                            if random.random() < 0.18:
                                chosen = ("heroic_raise", None)
                            elif random.random() < 0.30:
                                chosen = ("ruby_shield", None)
                            else:
                                targets = [i for i,p in enumerate(self.player_team) if p.is_alive()]
                                chosen = ("attack", random.choice(targets)) if targets else ("none", None)
                        elif actor.shortname == "CA":
                            r = random.random()
                            if r < 0.22:
                                chosen = ("sneak_boost", None)
                            elif r < 0.38:
                                targets = [i for i,p in enumerate(self.player_team) if p.is_alive()]
                                chosen = ("vital_stab", random.choice(targets)) if targets else ("none", None)
                            else:
                                targets = [i for i,p in enumerate(self.player_team) if p.is_alive()]
                                chosen = ("attack", random.choice(targets)) if targets else ("none", None)
                        elif actor.shortname == "QK":
                            r = random.random()
                            if r < 0.18:
                                chosen = ("die_for_me", None)
                            elif r < 0.36:
                                chosen = ("kings_command", None)
                            else:
                                targets = [i for i,p in enumerate(self.player_team) if p.is_alive()]
                                chosen = ("attack", random.choice(targets)) if targets else ("none", None)
                        else:
                            targets = [i for i,p in enumerate(self.player_team) if p.is_alive()]
                            chosen = ("attack", random.choice(targets)) if targets else ("none", None)
                else:
                    if actor.shortname == "EA" and random.random() < 0.25:
                        chosen = ("arrow_shower", None)
                    else:
                        targets = [i for i,p in enumerate(self.player_team) if p.is_alive()]
                        chosen = ("attack", random.choice(targets)) if targets else ("none", None)

                # Enforce status-repeat rule
                if is_status_move(chosen[0]) and actor.last_status_move == chosen[0]:
                    if attempt > 20:
                        targets = [i for i,p in enumerate(self.player_team) if p.is_alive()]
                        chosen = ("attack", random.choice(targets)) if targets else ("none", None)
                        break
                    continue
                break

            # Reserve heal uses for CPU (decrement)
            if chosen[0] in ("heal_single", "heal_all"):
                if cpu_heal_left > 0:
                    cpu_heal_left -= 1
                else:
                    targets = [i for i,p in enumerate(self.player_team) if p.is_alive()]
                    chosen = ("attack", random.choice(targets)) if targets else ("none", None)

            actions[idx] = chosen

        self.cpu_actions = actions
        self.cpu_heal_left = cpu_heal_left

    def set_player_actions(self, actions):
        """
        actions: list of length len(self.player_team). Each entry: ("attack", target_idx) or ("heroic_raise",None) etc.
        Should be validated by UI; we also enforce status-repeat server-side (return False if invalid).
        """
        # Validate length
        if len(actions) != len(self.player_team):
            raise ValueError("actions length mismatch")

        # Validate legality (status-repeat): cannot use same non-attack twice in a row
        for idx, act in enumerate(actions):
            if act is None:
                actions[idx] = ("none", None)
                continue
            name, param = act
            if is_status_move(name):
                if self.player_team[idx].last_status_move == name:
                    return False, f"{self.player_team[idx].name} cannot use {name} twice in a row."
        # All good — store
        self.player_actions = actions
        return True, "ok"

    def resolve_round(self):
        """
        Resolves one round: heals first, then all non-heal actions sorted by effective speed (ties -> diceroll),
        applying all move effects and decrementing durations at end of round.
        """
        self.log.append(f"--- Round {self.round_number} ---")

        # Reset acted flag
        for c in self.player_team + self.cpu_team:
            c.acted_this_round = False

        # 1) HEAL PHASE: execute all chosen heals first (player then cpu)
        # Player heals
        for i, act in enumerate(self.player_actions):
            actor = self.player_team[i]
            if not actor.is_alive() or act is None:
                continue
            name, param = act
            if name == "heal_all" and self.player_heal_left > 0:
                for c in self.player_team:
                    if c.is_alive():
                        c.heal_amount(int(c.max_hp * 0.30))
                self.player_heal_left -= 1
                actor.last_status_move = "heal_all"
                self.log.append(f"[Player] {actor.name} used Heal Ring -> Heal All (30%).")
            elif name == "heal_single" and self.player_heal_left > 0:
                if param is None or not (0 <= param < len(self.player_team)):
                    self.log.append(f"[Player] {actor.name} attempted Heal Ring (single) but target invalid.")
                else:
                    self.player_team[param].heal_amount(int(self.player_team[param].max_hp * 0.75))
                    self.player_heal_left -= 1
                    actor.last_status_move = "heal_single"
                    self.log.append(f"[Player] {actor.name} used Heal Ring -> Heal One on {self.player_team[param].name} (75%).")

        # CPU heals: ensure cpu_actions populated
        for i, act in enumerate(self.cpu_actions):
            actor = self.cpu_team[i]
            if not actor.is_alive() or act is None:
                continue
            name, param = act
            if name == "heal_all" and self.cpu_heal_left > 0:
                for c in self.cpu_team:
                    if c.is_alive():
                        c.heal_amount(int(c.max_hp * 0.30))
                self.cpu_heal_left -= 1
                actor.last_status_move = "heal_all"
                self.log.append(f"[CPU] {actor.name} used Heal Ring -> Heal All (30%).")
            elif name == "heal_single" and self.cpu_heal_left > 0:
                if param is None or not (0 <= param < len(self.cpu_team)):
                    self.log.append(f"[CPU] {actor.name} attempted Heal Ring (single) but target invalid.")
                else:
                    self.cpu_team[param].heal_amount(int(self.cpu_team[param].max_hp * 0.75))
                    self.cpu_heal_left -= 1
                    actor.last_status_move = "heal_single"
                    self.log.append(f"[CPU] {actor.name} used Heal Ring -> Heal One on {self.cpu_team[param].name} (75%).")

        # 2) Collect non-heal actions and resolve by speed order
        action_entries = []
        # add player actions
        for idx, act in enumerate(self.player_actions):
            actor = self.player_team[idx]
            if not actor.is_alive() or act is None:
                continue
            name, param = act
            if name in ("heal_all", "heal_single"):
                continue
            action_entries.append((actor, "player", act, actor.effective_speed(), diceroll(1,100), idx))

        # add cpu actions
        for idx, act in enumerate(self.cpu_actions):
            actor = self.cpu_team[idx]
            if not actor.is_alive() or act is None:
                continue
            name, param = act
            if name in ("heal_all", "heal_single"):
                continue
            action_entries.append((actor, "cpu", act, actor.effective_speed(), diceroll(1,100), idx))

        # sort by speed desc, tie by tie_roll desc
        action_entries.sort(key=lambda x: (x[3], x[4]), reverse=True)

        # Resolve actions in order
        for entry in action_entries:
            actor, team_label, action, eff_spd, tie, actor_idx = entry
            if not actor.is_alive():
                continue
            if actor.acted_this_round:
                continue
            if actor.stunned:
                self.log.append(f"{actor.name} is stunned and cannot act this round.")
                actor.stunned = False
                actor.acted_this_round = True
                continue

            name, param = action
            allies = self.player_team if team_label == "player" else self.cpu_team
            opponents = self.cpu_team if team_label == "player" else self.player_team

            # Status move record after action
            if is_status_move(name):
                actor.last_status_move = name

            # Team prefix for logs
            prefix = "[YOU]" if team_label == "player" else "[CPU]"
            
            # Handle each action
            if name == "attack":
                # choose fallback target
                alive_targets = [i for i,t in enumerate(opponents) if t.is_alive()]
                if not alive_targets:
                    actor.acted_this_round = True
                    continue
                if param is None or param not in alive_targets:
                    param = random.choice(alive_targets)
                target = opponents[param]

                # REDIRECTION: Die For Me - if target is QK, and some protector marked on target's team, redirect
                if target.shortname == "QK":
                    protectors = [p for p in opponents if p.take_hit_for_qk and p.is_alive() and p.shortname != "QK"]
                    if protectors:
                        protector = protectors[0]  # there should be at most one
                        protector.take_hit_for_qk = False
                        target = protector
                        self.log.append(f"{prefix} {protector.name} takes the hit for {opponents[param].name} (QK).")

                # compute damage
                if actor.shortname == "RW":
                    dmg, crit = rw_attack(actor, target)
                elif actor.shortname == "EA":
                    dmg, crit = ea_attack(actor, target)
                elif actor.shortname == "TB":
                    dmg, crit = tb_attack(actor, target)
                elif actor.shortname == "CA":
                    dmg, crit = ca_attack(actor, target)
                elif actor.shortname == "QK":
                    dmg, crit = qk_attack(actor, target)
                else:
                    from characters import compute_attack_damage
                    dmg, crit = compute_attack_damage(actor, target, 50, 60)

                target.take_damage(dmg)
                self.log.append(f"{prefix} {actor.name} attacks {target.name} for {dmg}{' (CRIT)' if crit else ''}.")
                actor.acted_this_round = True

            elif name == "heroic_raise":
                rw_heroic_raise(allies)
                self.log.append(f"{prefix} {actor.name} uses Heroic Raise.")
                actor.acted_this_round = True

            elif name == "ruby_shield":
                rw_ruby_shield(actor)
                self.log.append(f"{prefix} {actor.name} uses Ruby Shield.")
                actor.acted_this_round = True

            elif name == "arrow_shower":
                hits = ea_arrow_shower(opponents)
                for targ, dmg in hits:
                    self.log.append(f"  → {targ.name} takes {dmg} AoE damage.")
                self.log.append(f"{prefix} {actor.name} uses Arrow Shower.")
                actor.acted_this_round = True

            elif name == "sharp_aim":
                ea_sharp_aim(actor)
                self.log.append(f"{prefix} {actor.name} uses Sharp Aim (guarantees next crit).")
                actor.acted_this_round = True

            elif name == "shiny_flex":
                tb_shiny_flex(actor)
                self.log.append(f"{prefix} {actor.name} uses Shiny Flex.")
                actor.acted_this_round = True

            elif name == "stun_punch":
                alive_targets = [i for i,t in enumerate(opponents) if t.is_alive()]
                if not alive_targets:
                    actor.acted_this_round = True
                    continue
                if param is None or param not in alive_targets:
                    param = random.choice(alive_targets)
                target = opponents[param]
                dmg = tb_stun_punch(actor, target)
                self.log.append(f"{prefix} {actor.name} hits {target.name} with Stun Punch for {dmg} and stuns them.")
                actor.acted_this_round = True

            elif name == "vital_stab":
                alive_targets = [i for i,t in enumerate(opponents) if t.is_alive()]
                if not alive_targets:
                    actor.acted_this_round = True
                    continue
                if param is None or param not in alive_targets:
                    param = random.choice(alive_targets)
                target = opponents[param]
                dmg, heal_amt = ca_vital_stab(actor, target)
                self.log.append(f"{prefix} {actor.name} uses Vital Stab on {target.name} for {dmg} damage and heals {heal_amt} HP.")
                actor.acted_this_round = True

            elif name == "sneak_boost":
                ca_sneak_boost(allies)
                self.log.append(f"{prefix} {actor.name} uses Sneak Boost.")
                actor.acted_this_round = True

            elif name == "die_for_me":
                prot = qk_die_for_me(actor, allies)
                if prot:
                    self.log.append(f"{prefix} {actor.name} uses Die For Me: {prot.name} will absorb the first hit aimed at {actor.name} next turn.")
                else:
                    self.log.append(f"{prefix} {actor.name} tried to use Die For Me but it failed (no available protector).")
                actor.acted_this_round = True

            elif name == "kings_command":
                ok = qk_kings_command(actor)
                if not ok:
                    self.log.append(f"{prefix} {actor.name} tried to use King's Command but buff already active — move fails.")
                else:
                    self.log.append(f"{prefix} {actor.name} uses King's Command: +20% damage & +20% resist for 2 turns.")
                actor.acted_this_round = True

            else:
                actor.acted_this_round = True
                continue

        # End of round: decrement durations
        for c in self.player_team + self.cpu_team:
            if c.team_crit_buff_turns > 0:
                c.team_crit_buff_turns -= 1
            if c.crit_immune_turns > 0:
                c.crit_immune_turns -= 1
            if c.damage_resist_turns > 0:
                c.damage_resist_turns -= 1
            if c.team_speed_buff_turns > 0:
                c.team_speed_buff_turns -= 1
                if c.team_speed_buff_turns == 0:
                    c.team_speed_bonus = 0
            if c.damage_buff_turns > 0:
                c.damage_buff_turns -= 1
            if c.resist_buff_turns > 0:
                c.resist_buff_turns -= 1

        # Clear any remaining stun markers? (stun is consumed when used earlier)
        self.round_number += 1

        return True

    # convenience getters for UI
    def get_player_team(self):
        return self.player_team

    def get_cpu_team(self):
        return self.cpu_team

    def get_log(self, n=20):
        return self.log[-n:]

    def cpu_pick_random_team_indices(self):
        return random.sample(range(len(self.cpu_prototypes)), 3)
