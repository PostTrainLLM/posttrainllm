#!/usr/bin/env python3
"""
Map external HuggingFace datasets to Pace's 7 intent classes:
  - pureKnowledge: factual questions, definitions, weather, time
  - screenDescription: "what am I looking at" style
  - screenAction: do something on the device (click, open, play, volume, etc.)
  - chitchat: greetings, jokes, social filler
  - phoneLargeModel: explicit escalation ("ask chatgpt", "use cloud")
  - research: compare, investigate, deep look
  - unknown: out-of-scope, not applicable to Mac assistant

Pace's classes are Mac-assistant-specific. Many external intents are
smart-home or banking — those map to "unknown" because they're not
actions Pace can perform on a Mac.
"""

import json
import random
import os

random.seed(42)

OUTPUT_FILE = "data/external/pace_mapped_external.jsonl"

# ─── CLINC150 mapping ─────────────────────────────────────────────
# 150 in-scope intents + OOS. Map by semantic fit to Pace.
CLINC150_MAP = {
    # → pureKnowledge (factual questions)
    "restaurant_reviews": "pureKnowledge",
    "nutrition_info": "pureKnowledge",
    "oil_change_how": "pureKnowledge",
    "time": "pureKnowledge",
    "weather": "pureKnowledge",
    "interest_rate": "pureKnowledge",
    "gas_type": "pureKnowledge",
    "measurement_conversion": "pureKnowledge",
    "date": "pureKnowledge",
    "definition": "pureKnowledge",
    "fun_fact": "pureKnowledge",
    "recipe": "pureKnowledge",
    "ingredients_list": "pureKnowledge",
    "ingredient_substitution": "pureKnowledge",
    "calories": "pureKnowledge",
    "cook_time": "pureKnowledge",
    "mpg": "pureKnowledge",
    "tire_pressure": "pureKnowledge",
    "expiration_date": "pureKnowledge",
    "exchange_rate": "pureKnowledge",
    "credit_score": "pureKnowledge",
    "income": "pureKnowledge",
    "taxes": "pureKnowledge",
    "timezone": "pureKnowledge",
    "flight_status": "pureKnowledge",
    "distance": "pureKnowledge",
    "directions": "pureKnowledge",
    "traffic": "pureKnowledge",
    "how_busy": "pureKnowledge",
    "vaccines": "pureKnowledge",
    "plug_type": "pureKnowledge",
    "spelling": "pureKnowledge",
    "translate": "pureKnowledge",
    "what_song": "pureKnowledge",
    "next_holiday": "pureKnowledge",
    "travel_alert": "pureKnowledge",
    "travel_suggestion": "pureKnowledge",
    "restaurant_suggestion": "pureKnowledge",
    "meal_suggestion": "pureKnowledge",
    "shopping_list": "pureKnowledge",  # query existing list
    "todo_list": "pureKnowledge",  # query existing list
    "meeting_schedule": "pureKnowledge",
    "calendar": "pureKnowledge",
    "current_location": "pureKnowledge",
    "share_location": "pureKnowledge",
    "pto_balance": "pureKnowledge",
    "pto_request_status": "pureKnowledge",
    "pto_used": "pureKnowledge",
    "payday": "pureKnowledge",
    "bill_balance": "pureKnowledge",
    "bill_due": "pureKnowledge",
    "bill_balance": "pureKnowledge",
    "transactions": "pureKnowledge",
    "spending_history": "pureKnowledge",
    "balance": "pureKnowledge",
    "routing": "pureKnowledge",
    "rewards_balance": "pureKnowledge",
    "order_status": "pureKnowledge",
    "application_status": "pureKnowledge",
    "credit_limit": "pureKnowledge",
    "apr": "pureKnowledge",
    "min_payment": "pureKnowledge",
    "direct_deposit": "pureKnowledge",
    "rollover_401k": "pureKnowledge",
    "w2": "pureKnowledge",
    "international_fees": "pureKnowledge",
    "international_visa": "pureKnowledge",
    "insurance": "pureKnowledge",
    "last_maintenance": "pureKnowledge",
    "replacement_card_duration": "pureKnowledge",
    "lost_luggage": "pureKnowledge",
    "gas": "pureKnowledge",

    # → screenAction (device actions Pace can do on a Mac)
    "play_music": "screenAction",
    "next_song": "screenAction",
    "update_playlist": "screenAction",
    "change_volume": "screenAction",
    "whisper_mode": "screenAction",
    "alarm": "screenAction",
    "timer": "screenAction",
    "reminder": "screenAction",
    "reminder_update": "screenAction",
    "calendar_update": "screenAction",
    "todo_list_update": "screenAction",
    "shopping_list_update": "screenAction",
    "make_call": "screenAction",
    "text": "screenAction",
    "cancel": "screenAction",
    "cancel_reservation": "screenAction",
    "book_flight": "screenAction",
    "book_hotel": "screenAction",
    "car_rental": "screenAction",
    "restaurant_reservation": "screenAction",
    "accept_reservations": "screenAction",
    "order": "screenAction",
    "order_checks": "screenAction",
    "pay_bill": "screenAction",
    "transfer": "screenAction",
    "freeze_account": "screenAction",
    "report_fraud": "screenAction",
    "report_lost_card": "screenAction",
    "damaged_card": "screenAction",
    "new_card": "screenAction",
    "pin_change": "screenAction",
    "credit_limit_change": "screenAction",
    "insurance_change": "screenAction",
    "reset_settings": "screenAction",
    "change_accent": "screenAction",
    "change_ai_name": "screenAction",
    "change_language": "screenAction",
    "change_speed": "screenAction",
    "change_user_name": "screenAction",
    "sync_device": "screenAction",
    "schedule_maintenance": "screenAction",
    "schedule_meeting": "screenAction",
    "uber": "screenAction",
    "smart_home": "screenAction",
    "find_phone": "screenAction",
    "redeemRewards": "screenAction",

    # → chitchat (social filler, greetings, jokes)
    "greeting": "chitchat",
    "goodbye": "chitchat",
    "thank_you": "chitchat",
    "tell_joke": "chitchat",
    "flip_coin": "chitchat",
    "roll_dice": "chitchat",
    "yes": "chitchat",
    "no": "chitchat",
    "maybe": "chitchat",
    "repeat": "chitchat",
    "are_you_a_bot": "chitchat",
    "how_old_are_you": "chitchat",
    "what_are_your_hobbies": "chitchat",
    "what_can_i_ask_you": "chitchat",
    "what_is_your_name": "chitchat",
    "where_are_you_from": "chitchat",
    "who_do_you_work_for": "chitchat",
    "who_made_you": "chitchat",
    "meaning_of_life": "chitchat",
    "do_you_have_pets": "chitchat",
    "food_last": "chitchat",
    "calculator": "chitchat",  # simple utility, often chitchat-adjacent

    # → unknown (banking/account-specific, not Mac-assistant actions)
    "account_blocked": "unknown",
    "card_declined": "unknown",
    "user_name": "unknown",
    "improve_credit_score": "unknown",
    "carry_on": "unknown",
    "jump_start": "unknown",
    "tire_change": "unknown",
    "oil_change_when": "unknown",
    "travel_notification": "unknown",
    "pto_request": "unknown",
    "confirm_reservation": "unknown",
}

# ─── MASSIVE mapping ──────────────────────────────────────────────
MASSIVE_MAP = {
    # → pureKnowledge
    "datetime_query": "pureKnowledge",
    "datetime_convert": "pureKnowledge",
    "weather_query": "pureKnowledge",
    "qa_currency": "pureKnowledge",
    "qa_definition": "pureKnowledge",
    "qa_factoid": "pureKnowledge",
    "qa_maths": "pureKnowledge",
    "qa_stock": "pureKnowledge",
    "cooking_query": "pureKnowledge",
    "cooking_recipe": "pureKnowledge",
    "transport_query": "pureKnowledge",
    "transport_traffic": "transport_traffic",
    "calendar_query": "pureKnowledge",
    "lists_query": "pureKnowledge",
    "music_query": "pureKnowledge",
    "news_query": "pureKnowledge",
    "email_query": "pureKnowledge",
    "email_querycontact": "pureKnowledge",
    "social_query": "pureKnowledge",
    "takeaway_query": "pureKnowledge",
    "recommendation_events": "research",  # "recommend events" → research
    "recommendation_locations": "research",
    "recommendation_movies": "research",

    # → screenAction
    "play_music": "screenAction",
    "play_audiobook": "screenAction",
    "play_game": "screenAction",
    "play_podcasts": "screenAction",
    "play_radio": "screenAction",
    "audio_volume_up": "screenAction",
    "audio_volume_down": "screenAction",
    "audio_volume_mute": "screenAction",
    "audio_volume_other": "screenAction",
    "music_settings": "screenAction",
    "music_likeness": "screenAction",
    "music_dislikeness": "screenAction",
    "alarm_set": "screenAction",
    "alarm_query": "pureKnowledge",
    "alarm_remove": "screenAction",
    "calendar_set": "screenAction",
    "calendar_remove": "screenAction",
    "lists_createoradd": "screenAction",
    "lists_remove": "screenAction",
    "email_addcontact": "screenAction",
    "email_sendemail": "screenAction",
    "social_post": "screenAction",
    "takeaway_order": "screenAction",
    "transport_ticket": "screenAction",
    "transport_taxi": "screenAction",
    "iot_coffee": "screenAction",
    "iot_cleaning": "screenAction",
    "iot_hue_lightchange": "screenAction",
    "iot_hue_lightdim": "screenAction",
    "iot_hue_lightoff": "screenAction",
    "iot_hue_lighton": "screenAction",
    "iot_hue_lightup": "screenAction",
    "iot_wemo_off": "screenAction",
    "iot_wemo_on": "screenAction",

    # → chitchat
    "general_greet": "chitchat",
    "general_joke": "chitchat",
    "general_quirky": "unknown",  # quirky/off-topic → unknown

    # → unknown (not applicable to Mac)
    # (general_quirky already mapped above)
}

# Fix transport_traffic typo
MASSIVE_MAP["transport_traffic"] = "pureKnowledge"

# ─── OVOS mapping ─────────────────────────────────────────────────
OVOS_MAP = {
    # → pureKnowledge
    "weather:weather_forecast": "pureKnowledge",
    "weather:weather_today": "pureKnowledge",
    "weather:weather_humidity": "pureKnowledge",
    "weather:weather_wind": "pureKnowledge",
    "weather:weather_location": "pureKnowledge",
    "search_qa:define_word": "pureKnowledge",
    "search_qa:factual_query": "pureKnowledge",
    "search_qa:spell_word": "pureKnowledge",
    "search_qa:translate_phrase": "pureKnowledge",
    "search_qa:who_is": "pureKnowledge",
    "news:read_headlines": "pureKnowledge",
    "news:read_topic": "pureKnowledge",
    "news:news_source": "pureKnowledge",
    "navigation:eta_query": "pureKnowledge",
    "navigation:find_nearby": "pureKnowledge",
    "navigation:traffic_status": "pureKnowledge",
    "calendar:list_events": "pureKnowledge",
    "calendar:next_event": "pureKnowledge",
    "communication:read_messages": "pureKnowledge",

    # → screenAction
    "media:play_song": "screenAction",
    "media:pause_playback": "screenAction",
    "media:resume_playback": "screenAction",
    "media:set_volume": "screenAction",
    "media:skip_track": "screenAction",
    "calendar:create_event": "screenAction",
    "calendar:cancel_event": "screenAction",
    "calendar:reschedule_event": "screenAction",
    "communication:call_contact": "screenAction",
    "communication:send_message": "screenAction",
    "communication:video_call": "screenAction",
    "communication:hang_up": "screenAction",
    "timers_alarms:set_alarm": "screenAction",
    "timers_alarms:set_timer": "screenAction",
    "timers_alarms:cancel_timer": "screenAction",
    "timers_alarms:snooze_alarm": "screenAction",
    "timers_alarms:list_alarms": "pureKnowledge",
    "navigation:navigate_to": "screenAction",
    "navigation:cancel_route": "screenAction",
    "smarthome:lights_off": "screenAction",
    "smarthome:lights_on": "screenAction",
    "smarthome:set_brightness_light": "screenAction",
    "smarthome:set_thermostat": "screenAction",
    "smarthome:lock_door": "screenAction",
    "system_control:mute_system": "screenAction",
    "system_control:set_brightness_screen": "screenAction",
    "system_control:change_language": "screenAction",
    "system_control:restart": "screenAction",
    "system_control:shutdown": "screenAction",
    "news:next_story": "screenAction",
    "news:previous_story": "screenAction",

    # → unknown (OVOS OOD buckets: near_ood, far_ood, asr_noise, typos)
    # These are handled by split field, not intent name
}

# nfqa mapping
NFQA_MAP = {
    "FACTOID": "pureKnowledge",
    "DEBATE": "research",
    "EVIDENCE-BASED": "research",
    "INSTRUCTION": "screenAction",
    "REASON": "pureKnowledge",
    "EXPERIENCE": "pureKnowledge",
    "COMPARISON": "research",
    "NOT-A-QUESTION": "unknown",
}


def map_clinc150():
    """Map CLINC150 train + test to Pace intents."""
    examples = []
    for split_file in ["data/external/clinc150_train.jsonl",
                       "data/external/clinc150_test.jsonl"]:
        with open(split_file) as f:
            for line in f:
                ex = json.loads(line)
                if ex["is_oos"]:
                    examples.append({"text": ex["text"], "intent": "unknown"})
                else:
                    pace_intent = CLINC150_MAP.get(ex["intent_name"], "unknown")
                    examples.append({"text": ex["text"], "intent": pace_intent})
    return examples


def map_massive():
    """Map MASSIVE en-US to Pace intents."""
    examples = []
    for split_file in ["data/external/massive_enUS_train.jsonl",
                       "data/external/massive_enUS_validation.jsonl",
                       "data/external/massive_enUS_test.jsonl"]:
        with open(split_file) as f:
            for line in f:
                ex = json.loads(line)
                pace_intent = MASSIVE_MAP.get(ex["intent_name"], "unknown")
                examples.append({"text": ex["text"], "intent": pace_intent})
    return examples


def map_ovos():
    """Map OVOS en-US test to Pace intents. OOD buckets → unknown."""
    examples = []
    with open("data/external/ovos_enUS_test.jsonl") as f:
        for line in f:
            ex = json.loads(line)
            split = ex.get("split", "")
            if split in ("near_ood", "far_ood", "asr_noise", "typos"):
                examples.append({"text": ex["utterance"], "intent": "unknown"})
            else:
                intent = ex.get("expected_intent")
                if intent is None or intent == "None":
                    examples.append({"text": ex["utterance"], "intent": "unknown"})
                else:
                    pace_intent = OVOS_MAP.get(intent, "unknown")
                    examples.append({"text": ex["utterance"], "intent": pace_intent})
    return examples


def map_nfqa():
    """Map nfqa English to Pace intents."""
    examples = []
    with open("data/external/nfqa_en.jsonl") as f:
        for line in f:
            ex = json.loads(line)
            label = ex.get("ensemble_prediction", "NOT-A-QUESTION")
            pace_intent = NFQA_MAP.get(label, "unknown")
            examples.append({"text": ex["question"], "intent": pace_intent})
    return examples


def main():
    all_examples = []

    clinc = map_clinc150()
    print(f"CLINC150: {len(clinc)} examples")
    all_examples.extend(clinc)

    massive = map_massive()
    print(f"MASSIVE: {len(massive)} examples")
    all_examples.extend(massive)

    ovos = map_ovos()
    print(f"OVOS: {len(ovos)} examples")
    all_examples.extend(ovos)

    nfqa = map_nfqa()
    print(f"nfqa: {len(nfqa)} examples")
    all_examples.extend(nfqa)

    # Filter: skip empty texts
    all_examples = [e for e in all_examples if e["text"].strip()]
    print(f"\nTotal mapped: {len(all_examples)}")

    # Distribution
    from collections import Counter
    dist = Counter(e["intent"] for e in all_examples)
    print("\nDistribution:")
    for intent, count in sorted(dist.items(), key=lambda x: -x[1]):
        print(f"  {intent}: {count} ({100*count/len(all_examples):.1f}%)")

    # Shuffle
    random.shuffle(all_examples)

    with open(OUTPUT_FILE, "w") as f:
        for ex in all_examples:
            f.write(json.dumps(ex) + "\n")
    print(f"\nSaved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
