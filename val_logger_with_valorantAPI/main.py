import csv
import discord
import matplotlib.pyplot as plt
import numpy as np
import traceback
import os
import valorant
from constants import DC_TOKEN, VAL_TOKEN

# note of order of csv data
# dc_username, kda, acs, rr, duration, kills, deaths, assists, mapId, character, rounds_played, rating

# constants
prefix = "v!"
game_save_file = "backup_game_data.csv"
user_save_file = "backup_user_data.csv"
graph_image = "valorant_graph.png"

# global variables (yuck, but i must)
client = discord.Client()
val_client = valorant.Client(VAL_TOKEN)
dc_to_val_user = {}


class ValorantUser:
    def __init__(self, riot_name: str):
        self.game_counter = 0
        self.total_kills = 0
        self.total_deaths = 0
        self._data = []
        self.riot_name = riot_name
        self.most_recent_game_time = 0

    def get_data(self):
        return self._data[:]

    def register_game_api(self, rating: str, rr: str, match: valorant.MatchDTO):
        if match is None:
            return

        player = None
        for p in match.players:
            print(f"{p.gameName=} {p.tagLine=}")
            if p.gameName == self.riot_name:
                player = p
                break

        if player is None:
            return

        match = match.matchInfo
        game = player.stats

        if match is None or game is None or match.gameStartMillis <= self.most_recent_game_time:
            return

        self.most_recent_game_time = match.gameStartMillis
        new_game = ValorantGame(self, game.kda, game.averageScore, convert_rr(rr), match.gameLengthMillis,
                                game.kills, game.deaths, game.assists, match.mapId, player.characterId,
                                game.roundsPlayed, rating)
        self._data.append(new_game)
        return new_game

    def register_game_saved(self, row):
        self._data.append(ValorantGame(self, row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9],
                                       row[10], row[11]))


class ValorantGame:

    def __init__(self, user: ValorantUser, kda, acs, rr, duration, kills, deaths, assists, mapId, character,
                 rounds_played, rating):
        self._kda = kda
        self._acs = acs
        self._rr = rr
        self._duration = duration
        self._kills = kills
        self._deaths = deaths
        self._assists = assists
        self._map = mapId
        self._character = character
        self._rounds_played = rounds_played

        user.game_counter += 1
        self._game_counter = user.game_counter

        user.total_kills += self._kills
        user.total_deaths += self._deaths
        self._total_kills = user.total_kills
        self._total_deaths = user.total_deaths

        # calculating numerical representation of rating
        self._rating = rating
        self._rating_numerical = float(rating.split("/")[0])

    def get_attr(self, attribute: str):
        """
        Gets the specified attribute of the game. These could be ints or strings
        :param attribute: string of the attribute name we want
        :return: saved value of that attribute
        """
        if attribute == "kda":
            return self._kda
        if attribute == "acs":
            return self._acs
        if attribute == "rr":
            return self._rr
        if attribute == "duration":
            return self._duration
        if attribute == "rating":
            return self._rating_numerical
        if attribute == "kills":
            return self._kills
        if attribute == "deaths":
            return self._deaths
        if attribute == "assists":
            return self._assists
        if attribute == "games":
            return self._game_counter
        if attribute == "total_kills":
            return self._total_kills
        if attribute == "total_deaths":
            return self._total_deaths
        if attribute == "map":
            return self._map

    def csv_repr(self, username) -> list:
        return [username, self._kda, self._acs, self._rr, self._duration, self._kills, self._deaths, self._assists,
                self._map, self._character, self._rounds_played, self._rating]


@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))


@client.event
async def on_message(message):
    if message.author == client.user or not message.content.startswith(prefix):
        return

    msg = message.content[len(prefix):].strip()

    if msg.startswith("wakka"):
        await message.channel.send("<:wakkawakka:968379435231379536>")
        await message.channel.send("https://tenor.com/view/pacman-video-game-eating-marshmallow-gif-6008098")

    if msg.startswith("template"):
        # send a template so noah can easily copy paste and not have any errors
        await message.channel.send("v! log rr=*RR* rating=*XX.XX/11*\n(NOTE! these can be done out of order!) "
                                   "example:\n`v! log rr=s2_34 rating=8.25/11`")

    if msg.startswith("register"):
        username = message.author.mention
        riot_name = msg[8:].strip()
        dc_to_val_user[username] = ValorantUser(riot_name)
        await save_user_data(username, riot_name)
        await message.channel.send("registered new valorant user")

    if msg.startswith("help"):
        await message.channel.send("Hello there! Firstly, here are the valid commands:\n"
                                   "v! help - gives you this help message\n\n"
                                   "v! wakka - sends wakka emoji and gif\n\n"
                                   "v! template - sends the template message for logging data\n\n"
                                   "v! log - adds the data of a new game to our tracking "
                                   "system. You do not need to follow the template exactly, the data types can be "
                                   "entered in whatever order, but the spaces, dashes, and slashes should be "
                                   "maintained exactly.\n\n"
                                   "v! graph [type] [y]/[x] - this will send a graph. type, y, and x axes are "
                                   "optional. If provided, it will generate a graph of the specified axes. "
                                   "You can choose plot, scatter, step, pie, or histogram (pie and histogram only take "
                                   "x variable) as the type of the plot, default is plot (normal straight line graph). "
                                   "To graph the map you must use a pie chart If no parameters are given, "
                                   "I will send several graphs of the data you most likely want to see\n"
                                   "Here is a list of all data collected that can be used in graphs:\n"
                                   "```\nkda\nkills\ndeaths\nassists\ntotal_kills\ntotal_deaths\nacs\nrr\nmap\nrating"
                                   "\ntime\nduration\ngames"
                                   "```\nNow, some explanation of the data being stored. We store kda raw, but for "
                                   "graphs, it is calculated into the decimal form of k/d. Mental rating is similarly "
                                   "converted from xx/11 into the decimal representation. The time is stored as "
                                   "minutes or hours:minutes since 4am. For graphing purposes, the axes will be number "
                                   "of minutes since 4am (start time). When graphing time on an axis, we use the "
                                   "average of the start and end time to represent the 'exact' time of the game. "
                                   "Rank is stated in terms of [1 letter "
                                   "abbreviation for general rank][tier in rank]_[rr in rank]. g2_45 means "
                                   "gold 2, 45rr. These are again converted into a numerical representation. For this, "
                                   "we call iron 0, 0rr to be absolute 0. From there, each tier is 100 rr, and the "
                                   "mid-tier rr is added. so g2_45 is converted to 1045.\n\n")

    if msg == "graph":
        data = dc_to_val_user[message.author.mention].get_data()
        await send_graph(message, "games", "rr", "step", data)
        await send_graph(message, "games", "acs", "scatter", data)
        await send_graph(message, "games", "kda", "scatter", data)
        await send_graph(message, "games", "rating", "plot", data)
        await send_graph(message, "games", "total_kills", "plot", data)

    elif msg.startswith("graph"):
        msg = msg[5:].strip().split()
        data = dc_to_val_user[message.author.mention].get_data()

        # TODO: graph_settings
        graph_settings = {"graph_type": "plot", "graph_data": "rr/games", "graph_user_mention": message.author.mention}

        graph_type = "plot"
        if len(msg) > 1:
            graph_type = msg[0]
            msg = msg[1].strip()

            if graph_type == "pie" or graph_type == "histogram":
                await send_graph(message, msg, "time", graph_type, data)  # we ignore this time data
                return
        else:
            msg = msg[0]

        axes = msg.split("/")
        x_axis = axes[1]
        y_axis = axes[0]
        await send_graph(message, x_axis, y_axis, graph_type, data)

    if msg.startswith("log"):
        try:
            msg_split = msg[3:].split()  # [3:] to remove "log"
            new_game_data = {"rr": None, "rating": None}

            for data_entry in msg_split:
                data_split = data_entry.split("=")
                data_title = data_split[0]
                data_value = data_split[1]
                if data_title in new_game_data:
                    new_game_data[data_title] = data_value

            # verify nothing was left out
            for value in new_game_data.values():
                if value is None:
                    # here we have an error
                    await message.channel.send(
                        f"{message.author.mention}! You did not enter all the types of data I need")
                    return

            username = message.author.mention
            val_user = dc_to_val_user[username]
            account = val_client.get_user_by_name(val_user.riot_name)
            if account is None:
                return

            match_list = account.matchlist().history
            match_list.sort(key=lambda x: x.gameStartMillis)

            for match in match_list:
                game = val_user.register_game_api(new_game_data["rating"], new_game_data["rr"], match.get())
                await save_game_data(game, username)

            await message.channel.send("successfully added the data")

        except Exception as e:
            await message.channel.send(f"{message.author.mention}! There was an error entering the data, try again. "
                                       f"Or maybe something is broken (oh no!)")
            await message.channel.send(e)
            print(e)
            traceback.print_exc()


async def send_graph(message, x_axis_name: str, y_axis_name: str, graph_type, data) -> None:
    """
    This creates a graph and then sends it in discord
    :param data: the data from the specific user we are looking at
    :param message: discord message to we can send the file
    :param x_axis_name: x-axis name
    :param y_axis_name: y-axis name
    :param graph_type: the type, default is plot, but it can be scatter
    :return: None, instead we send a graph in discord
    """
    await create_graph(x_axis_name, y_axis_name, graph_type, data)
    await message.channel.send("", file=discord.File(graph_image))


async def create_graph(x_axis_name: str, y_axis_name: str, graph_type, data) -> None:
    """
    This creates the graph and saves it to a file to send
    :param data: the data from the specific user we are looking at
    :param x_axis_name: x-axis name
    :param y_axis_name: y-axis name
    :param graph_type: the type, default is plot, but it can be scatter
    :return: None, instead we send a graph in discord
    """
    if os.path.exists(graph_image):
        os.remove(graph_image)

    x_data = [game.get_attr(x_axis_name) for game in data]
    y_data = [game.get_attr(y_axis_name) for game in data]

    if graph_type == "pie":
        colors = plt.get_cmap('Blues')(np.linspace(0.2, 0.7, len(x_data)))
        labels = []
        [labels.append(x) for x in x_data if x not in labels]
        counts = [x_data.count(x) for x in labels]
        plt.pie(counts, colors=colors, labels=labels)
        plt.title(x_axis_name)
        plt.savefig(graph_image)
        plt.close()
        return
    if graph_type == "histogram":
        plt.hist(x_data, color='blue', bins=10)
        plt.title(x_axis_name)
        plt.savefig(graph_image)
        plt.close()
        return

    # best fit line
    coeff_linear_x, cov_x = np.polyfit(x_data, y_data, 1, cov=True)
    best_fit = [coeff_linear_x[0] * x + coeff_linear_x[1] for x in x_data]
    plt.plot(x_data, best_fit, label='Best Fit Line', color='green', linestyle='dashed')

    # picking different plot types
    if graph_type == "plot":
        plt.plot(x_data, y_data, label='True Results', color='blue')
    if graph_type == "scatter":
        plt.scatter(x_data, y_data, label='True Results', color='blue')
    if graph_type == "step":
        plt.step(x_data, y_data, label='True Results', color='blue')

    plt.legend()
    plt.ylabel(y_axis_name)
    plt.xlabel(x_axis_name)
    plt.title(x_axis_name + " vs. " + y_axis_name)
    plt.savefig(graph_image)
    plt.close()


def convert_rr(rr: str) -> int:
    """
    This takes the current valorant rank and converts it to the integer form of its entire rr.
    :param rr: in the form of [rank][tier]_[rr], like g2_45 is gold 2, 45rr
    :return: integer of total rr. g2_45 returns 45. 900 for gold, +100 for gold2, +45 for 45rr
    """
    rank = rr[0]
    tier = int(rr[1])
    mid_tier_rr = int(rr.split('_')[1])

    rank_rr = 0
    if rank == 'b':
        rank_rr = 300
    if rank == 's':
        rank_rr = 600
    if rank == 'g':
        rank_rr = 900
    if rank == 'p':
        rank_rr = 1200
    if rank == 'd':
        rank_rr = 1500
    if rank == 'a':
        rank_rr = 1800

    tier_bonus = 100 * (tier - 1)
    return rank_rr + tier_bonus + mid_tier_rr


async def save_game_data(game, username) -> None:
    """
    This saves the newly created game
    :param username: to associate data with dc user
    :param game: valorant game which holds all needed csv data
    :return: Nothing, this saves to a file
    """
    with open(game_save_file, 'a') as file:
        writer = csv.writer(file)
        writer.writerow(game.csv_repr(username))


async def save_user_data(username, val_name) -> None:
    """
    This saves the newly created game
    :param val_name: valorant name that belongs to this user
    :param username: to associate data with dc user
    :return: Nothing, this saves to a file
    """
    with open(user_save_file, 'a') as file:
        writer = csv.writer(file)
        writer.writerow([username, val_name])


def load_game_data():
    """
    This reads previous game data into a csv in case the bot crashes.
    :return: None, but the data will be saved in the global data variable
    """

    try:
        with open(game_save_file, 'r') as file:
            reader = csv.reader(file)
            next(reader)  # skip the field names

            for row in reader:
                username = row[0]
                val_user = dc_to_val_user[username]
                val_user.register_game_saved(row)

    except FileNotFoundError:
        with open(game_save_file, 'w') as file:
            writer = csv.writer(file)
            writer.writerow(["dc_username", "kda", "acs", "rr", "time", "rating", "duration", "game_counter", "map"])


def load_user_data():
    try:
        with open(user_save_file, 'r') as file:
            reader = csv.reader(file)
            next(reader)  # skip the field names

            for row in reader:
                username = row[0]
                dc_to_val_user[username] = ValorantUser(row[1])

    except FileNotFoundError:
        with open(user_save_file, 'w') as file:
            writer = csv.writer(file)
            writer.writerow(["dc_username", "riot_name"])


def main() -> None:
    load_user_data()
    load_game_data()
    client.run(DC_TOKEN)


if __name__ == '__main__':
    main()
