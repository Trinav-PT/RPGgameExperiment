# app.py
import streamlit as st
from characters import create_all_characters, clone_character, Character
from engine import BattleEngine
import random

st.set_page_config(page_title="Turn-Based Battle", layout="wide")
st.title("Turn-Based Battle Simulator")

# Load prototypes
prototypes = create_all_character_prototypes(prefix="")

# Setup session state
if "engine" not in st.session_state:
    # instantiate a BattleEngine with prototypes as both player and CPU choices
    eng = BattleEngine(prototypes, prototypes)
    st.session_state.engine = eng
    st.session_state.phase = "team_select"  # phases: team_select, in_battle
    st.session_state.selected_indices = []
    st.session_state.player_action_choices = {}  # idx -> (action, param)
    st.session_state.last_error = ""

engine: BattleEngine = st.session_state.engine

# Helper UI: show character card
def char_card(c):
    cols = st.columns([1,4])
    with cols[0]:
        st.write("")  # placeholder for image
    with cols[1]:
        st.markdown(f"**{c.name}**")
        st.write(f"HP: {c.hp}/{c.max_hp}")
        st.write(f"SPD: {c.effective_speed()}")
        flags = []
        if c.stunned: flags.append("STUNNED")
        if c.team_crit_buff_turns>0: flags.append(f"CRITBUFF:{c.team_crit_buff_turns}")
        if c.team_speed_buff_turns>0: flags.append(f"SPEED+{c.team_speed_bonus}:{c.team_speed_buff_turns}")
        if c.damage_buff_turns>0: flags.append(f"DMG+:{c.damage_buff_turns}")
        if c.resist_buff_turns>0: flags.append(f"RES+:{c.resist_buff_turns}")
        if flags:
            st.write(" | ".join(flags))

# Team selection screen
if st.session_state.phase == "team_select":
    st.subheader("Pick your 3 characters")
    prot_list = prototypes
    cols = st.columns([1,1,1,1,1])
    selections = []
    for i, p in enumerate(prot_list):
        with cols[i]:
            st.markdown(f"**{i}. {p.name}**")
            st.write(f"HP {p.max_hp} SPD {p.base_speed}")
            if st.button(f"Select {i}", key=f"sel_{i}"):
                # toggle selection
                if i in st.session_state.selected_indices:
                    st.session_state.selected_indices.remove(i)
                else:
                    if len(st.session_state.selected_indices) < 3:
                        st.session_state.selected_indices.append(i)
                    else:
                        st.warning("You already selected 3. Deselect to pick another.")
    st.write("Selected indices:", st.session_state.selected_indices)
    if st.button("Start Battle") and len(st.session_state.selected_indices) == 3:
        # pick CPU team randomly
        cpu_indices = engine.cpu_pick_random_team_indices()
        engine.start_battle(st.session_state.selected_indices, cpu_indices)
        st.session_state.phase = "in_battle"
        st.session_state.player_action_choices = {}
        st.experimental_rerun()
    elif st.button("Start Quick Battle (random)"):
        player_indices = random.sample(range(len(prototypes)), 3)
        cpu_indices = engine.cpu_pick_random_team_indices()
        engine.start_battle(player_indices, cpu_indices)
        st.session_state.phase = "in_battle"
        st.session_state.player_action_choices = {}
        st.experimental_rerun()
    st.stop()

# In-battle UI
player_team = engine.get_player_team()
cpu_team = engine.get_cpu_team()

col_left, col_right = st.columns([3,2])

with col_left:
    st.subheader("Your Team")
    for i, c in enumerate(player_team):
        with st.expander(f"{i}. {c.name}  — {c.hp}/{c.max_hp} HP"):
            char_card(c)

with col_right:
    st.subheader("CPU Team")
    for i, c in enumerate(cpu_team):
        st.write(f"{i}. {c.name} — {c.hp}/{c.max_hp} HP")

st.markdown("---")
st.subheader("Choose moves for your team (for all 3 characters)")

# Build UI for selecting actions
move_names_map = {
    "RW": { "1":"attack", "2":"heroic_raise", "3":"ruby_shield" },
    "EA": { "1":"attack", "2":"arrow_shower", "3":"sharp_aim" },
    "TB": { "1":"attack", "2":"shiny_flex", "3":"stun_punch" },
    "CA": { "1":"attack", "2":"vital_stab", "3":"sneak_boost" },
    "QK": { "1":"attack", "2":"die_for_me", "3":"kings_command" }
}

player_choices = {}
player_errors = []

for idx, ch in enumerate(player_team):
    if not ch.is_alive():
        st.info(f"{idx}. {ch.name} is down.")
        continue
    st.markdown(f"**{idx}. {ch.name}**")
    options = []
    options.append("1) Attack")
    if ch.shortname in move_names_map:
        options.append(f"2) {move_names_map[ch.shortname]['2']}")
        options.append(f"3) {move_names_map[ch.shortname]['3']}")
    heal_label = f"4) Heal Ring (left {engine.player_heal_left})"
    options.append(heal_label)

    sel = st.radio(f"Select move for {ch.name}", options, key=f"move_{idx}")

    # Map selection to action tuple
    if sel.startswith("1"):
        # Attack target selection
        alive_indices = [i for i, e in enumerate(cpu_team) if e.is_alive()]
        if not alive_indices:
            player_choices[idx] = ("none", None)
        else:
            target = st.selectbox(f"Choose target for {ch.name}", alive_indices, key=f"target_{idx}")
            player_choices[idx] = ("attack", int(target))
    elif sel.startswith("2"):
        act = move_names_map[ch.shortname]["2"]
        if act == "vital_stab":
            alive_indices = [i for i, e in enumerate(cpu_team) if e.is_alive()]
            if not alive_indices:
                player_choices[idx] = ("none", None)
            else:
                target = st.selectbox(f"Choose target for Vital Stab ({ch.name})", alive_indices, key=f"vital_target_{idx}")
                player_choices[idx] = ("vital_stab", int(target))
        else:
            player_choices[idx] = (act, None)
    elif sel.startswith("3"):
        act = move_names_map[ch.shortname]["3"]
        if act == "stun_punch":
            alive_indices = [i for i, e in enumerate(cpu_team) if e.is_alive()]
            if not alive_indices:
                player_choices[idx] = ("none", None)
            else:
                target = st.selectbox(f"Choose target for Stun Punch ({ch.name})", alive_indices, key=f"stun_target_{idx}")
                player_choices[idx] = ("stun_punch", int(target))
        else:
            player_choices[idx] = (act, None)
    else:
        # heal option -> choose all or single
        if engine.player_heal_left <= 0:
            st.warning("No Heal Rings left — default to Attack on first alive CPU.")
            alive_indices = [i for i, e in enumerate(cpu_team) if e.is_alive()]
            player_choices[idx] = ("attack", alive_indices[0] if alive_indices else None)
        else:
            heal_mode = st.radio(f"Heal mode for {ch.name}", ["a) Heal All (30%)", "b) Heal One (75%)"], key=f"hm_{idx}")
            if heal_mode.startswith("a"):
                player_choices[idx] = ("heal_all", None)
            else:
                ally_indices = [i for i, a in enumerate(player_team)]
                t = st.selectbox(f"Choose ally to heal for {ch.name}", ally_indices, key=f"heal_target_{idx}")
                player_choices[idx] = ("heal_single", int(t))

# Validate status-repeat rule client-side and show errors
valid = True
for idx, act in player_choices.items():
    ch = player_team[idx]
    name, param = act
    if is_status_move(name) and ch.last_status_move == name:
        player_errors.append(f"{ch.name} cannot use {name} twice in a row.")
        valid = False

if player_errors:
    for e in player_errors:
        st.error(e)

# Buttons: Commit player moves & execute turn
col1, col2 = st.columns([1,1])
with col1:
    if st.button("Confirm Moves (lock in)"):
        # Attempt to set actions on engine
        # Convert heal_single label to engine action name "heal_single" to match engine code
        actions_list = []
        for i in range(len(player_team)):
            if i in player_choices:
                actions_list.append(player_choices[i])
            else:
                actions_list.append(("none", None))
        ok, msg = engine.set_player_actions(actions_list)
        if not ok:
            st.session_state.last_error = msg
            st.error(msg)
        else:
            # pick cpu actions and resolve
            engine._choose_cpu_actions()
            engine.resolve_round()
            st.experimental_rerun()

with col2:
    if st.button("Auto-play 1 Round (random moves)"):
        # choose random legal moves for player and resolve
        rand_actions = []
        for ch in player_team:
            if not ch.is_alive():
                rand_actions.append(("none", None))
                continue
            # pick random move that obeys status repeat
            attempt = 0
            while True:
                attempt += 1
                # moves: attack, two statuses, heal (if any)
                choices = []
                choices.append(("attack", None))
                if ch.shortname == "RW":
                    choices.append(("heroic_raise", None))
                    choices.append(("ruby_shield", None))
                elif ch.shortname == "EA":
                    choices.append(("arrow_shower", None))
                    choices.append(("sharp_aim", None))
                elif ch.shortname == "TB":
                    choices.append(("shiny_flex", None))
                    # choose a random target for stun later
                    alive = [i for i,e in enumerate(cpu_team) if e.is_alive()]
                    choices.append(("stun_punch", random.choice(alive) if alive else None))
                elif ch.shortname == "CA":
                    alive = [i for i,e in enumerate(cpu_team) if e.is_alive()]
                    choices.append(("vital_stab", random.choice(alive) if alive else None))
                    choices.append(("sneak_boost", None))
                elif ch.shortname == "QK":
                    choices.append(("die_for_me", None))
                    choices.append(("kings_command", None))

                if engine.player_heal_left > 0:
                    choices.append(("heal_all", None))
                pick = random.choice(choices)
                if is_status_move(pick[0]) and ch.last_status_move == pick[0]:
                    if attempt > 20:
                        pick = ("attack", random.choice([i for i,e in enumerate(cpu_team) if e.is_alive()]) )
                        break
                    continue
                break
            rand_actions.append(pick)
        engine.set_player_actions(rand_actions)
        engine._choose_cpu_actions()
        engine.resolve_round()
        st.experimental_rerun()

# show battle log
st.markdown("---")
st.subheader("Battle Log")
for line in reversed(engine.get_log(30)):
    st.write(line)

# End conditions
if engine.all_dead(engine.get_cpu_team()):
    st.success("All CPU characters defeated — YOU WIN!")
    if st.button("Restart"):
        st.session_state.phase = "team_select"
        st.session_state.selected_indices = []
        st.session_state.player_action_choices = {}
        st.session_state.engine = BattleEngine(prototypes, prototypes)
        st.experimental_rerun()

if engine.all_dead(engine.get_player_team()):
    st.error("All your characters are defeated — YOU LOSE.")
    if st.button("Restart"):
        st.session_state.phase = "team_select"
        st.session_state.selected_indices = []
        st.session_state.player_action_choices = {}
        st.session_state.engine = BattleEngine(prototypes, prototypes)
        st.experimental_rerun()
