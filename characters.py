# characters.py
import random
from copy import deepcopy

def diceroll(low, high):
    return random.randint(low, high)

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

class Character:
    def __init__(self, shortname, fullname, max_hp, base_speed, base_crit, crit_amp):
        self.shortname = shortname
        self.name = fullname
        self.max_hp = max_hp
        self.hp = max_hp
        self.base_speed = base_speed
        self.base_crit = base_crit
        self.crit_amp = crit_amp

        # Buffs / statuses
        self.crit_immune_turns = 0       # Ruby Shield
        self.damage_resist_turns = 0     # TB Shiny Flex (30% reduction)
        self.guaranteed_crit_turn = False
        self.stunned = False
        self.team_crit_buff_turns = 0    # Heroic Raise
        self.team_speed_buff_turns = 0   # CA Sneak Boost
        self.team_speed_bonus = 0

        # King's Command specific
        self.damage_buff_turns = 0       # +20% damage
        self.resist_buff_turns = 0       # +20% resistance

        # bookkeeping
        self.acted_this_round = False
        self.last_status_move = None     # name of last non-attack move (to enforce lockout)

        # Die For Me marker (QK)
        self.take_hit_for_qk = False

    def clone(self):
        return deepcopy(self)

    def is_alive(self):
        return self.hp > 0

    def effective_speed(self):
        return self.base_speed + (self.team_speed_bonus if self.team_speed_buff_turns > 0 else 0)

    def take_damage(self, amount):
        self.hp = clamp(self.hp - amount, 0, self.max_hp)

    def heal_amount(self, amount):
        self.hp = clamp(self.hp + amount, 0, self.max_hp)

    def __repr__(self):
        return f"{self.name} ({self.hp}/{self.max_hp} HP, SPD {self.effective_speed()})"

# Factory that returns prototypes
def create_all_character_prototypes(prefix=""):
    # Return prototypes (not clones) for selection
    return [
        Character("RW", f"{prefix} Ruby Warrior", 1250, 50, 10, 70),
        Character("EA", f"{prefix} Emerald Archer", 800, 80, 15, 65),
        Character("TB", f"{prefix} Topaz Brawler", 1500, 30, 5, 105),
        Character("CA", f"{prefix} Crystal Assassin", 700, 100, 25, 85),
        Character("QK", f"{prefix} Quartz King", 1300, 35, 5, 185),
    ]

# --- Attack wrappers that compute damage but do not mutate or print ---
def compute_attack_damage(user, target, low, high):
    """
    Returns (dmg, is_crit).
    Considers user's guaranteed crit, team crit buff (30%), target crit immunity,
    King's Command damage buff, target resist (King's Command) and damage_resist_turns (Shiny Flex).
    """
    dmg = diceroll(low, high)

    # determine crit
    if user.guaranteed_crit_turn:
        is_crit = True
    else:
        effective_crit = 30 if user.team_crit_buff_turns > 0 else user.base_crit
        is_crit = (random.random() < effective_crit / 100.0)

    if target.crit_immune_turns > 0:
        is_crit = False

    if is_crit:
        dmg = int(dmg * (1 + user.crit_amp / 100.0))

    # King's Command (attacker damage buff)
    if user.damage_buff_turns > 0:
        dmg = int(dmg * 1.20)

    # target King's Command resist (20% reduction)
    if target.resist_buff_turns > 0:
        dmg = int(dmg * 0.80)

    # Shiny Flex (30% reduction)
    if target.damage_resist_turns > 0:
        dmg = int(dmg * 0.7)

    # consume guaranteed crit
    if user.guaranteed_crit_turn:
        user.guaranteed_crit_turn = False

    return dmg, is_crit

# Per-character attack calls
def rw_attack(user, target):
    return compute_attack_damage(user, target, 200, 300)

def ea_attack(user, target):
    return compute_attack_damage(user, target, 100, 150)

def tb_attack(user, target):
    return compute_attack_damage(user, target, 400, 450)

def ca_attack(user, target):
    return compute_attack_damage(user, target, 200, 270)

def qk_attack(user, target):
    return compute_attack_damage(user, target, 250, 350)

# Status moves implemented as effects applied by engine; some convenience functions:
def rw_heroic_raise(allies):
    for a in allies:
        if a.is_alive():
            a.team_crit_buff_turns = 3

def rw_ruby_shield(actor):
    actor.crit_immune_turns = 5

def ea_arrow_shower(opponents):
    results = []
    for o in opponents:
        if o.is_alive():
            dmg = diceroll(50, 70)
            # target resist / shiny flex adjustments should be applied outside or here:
            if o.damage_resist_turns > 0:
                dmg = int(dmg * 0.7)
            if o.resist_buff_turns > 0:
                dmg = int(dmg * 0.8)
            o.take_damage(dmg)
            results.append((o, dmg))
    return results

def ea_sharp_aim(actor):
    actor.guaranteed_crit_turn = True

def tb_shiny_flex(actor):
    actor.damage_resist_turns = 2

def tb_stun_punch(actor, target):
    dmg = 90
    if target.damage_resist_turns > 0:
        dmg = int(dmg * 0.7)
    if target.resist_buff_turns > 0:
        dmg = int(dmg * 0.8)
    target.take_damage(dmg)
    target.stunned = True
    return dmg

def ca_vital_stab(actor, target):
    dmg = 60
    if target.damage_resist_turns > 0:
        dmg = int(dmg * 0.7)
    if target.resist_buff_turns > 0:
        dmg = int(dmg * 0.8)
    target.take_damage(dmg)
    heal_amt = int(actor.max_hp * 0.10)
    actor.heal_amount(heal_amt)
    return dmg, heal_amt

def ca_sneak_boost(allies):
    for a in allies:
        if a.is_alive():
            a.team_speed_buff_turns = 3
            a.team_speed_bonus = 20

def qk_die_for_me(actor, allies):
    alive_allies = [a for a in allies if a.is_alive() and a.shortname != "QK"]
    if not alive_allies:
        return None
    protector = max(alive_allies, key=lambda x: x.hp)
    protector.take_hit_for_qk = True
    return protector

def qk_kings_command(actor):
    # Option C: if buff already active -> fail
    if actor.damage_buff_turns > 0 or actor.resist_buff_turns > 0:
        return False
    actor.damage_buff_turns = 2
    actor.resist_buff_turns = 2
    return True
