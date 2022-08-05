# valorant.py provides some powerful helper functions
# for filtering data from the API. These snippets cover
# both simple and advanced use cases.

import os
import valorant
from constants import VAL_TOKEN

client = valorant.Client(VAL_TOKEN, locale=None)
lb = client.get_leaderboard(size=100)
top_player = lb.players.get_all()[0]
puuid = top_player.puuid
print(top_player)

player = client.get_player_by_name(top_player.gameName)
print(player)
print(player.matchlist())