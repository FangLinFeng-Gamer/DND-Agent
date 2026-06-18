from dataclasses import dataclass


@dataclass
class ConversationTurn:
    adventure_id: int
    player_input: str
