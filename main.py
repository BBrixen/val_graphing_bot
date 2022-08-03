import csv
import discord
import matplotlib.pyplot as plt
import numpy as np
import traceback
import os
from constants import DC_TOKEN

# note of order of csv data
# kda, acs, rr, time, rating, duration, game_counter, map

# constants
prefix = "v!"
save_file = "backup_data.csv"
graph_image = "valorant_graph.png"

# global variables (yuck, but i must)
client = discord.Client()
game_counter = 0
total_kills = 0
total_deaths = 0
latest_time = 0
data = []


class ValorantGame:
    def __init__(self, kda: str, acs: str, rr, time: str, rating: str, game_map: str):
        global game_counter, total_kills, total_deaths, latest_time

        self._kda = kda
        self._acs = int(acs)
        self._rating = rating
        self._map = game_map
        self._game_count = game_counter
        game_counter += 1

        if type(rr) is int:
            self._rr = rr
        else:
            self._rr = convert_rr(rr)

        # calculating all the time things
        self._time = time

        time = time.split('-')
        start = minutes_since_start(time[0])
        end = minutes_since_start(time[1])
        latest_time = end
        self._duration = end - start
        self._center_time = (end + start) // 2

        # calculating numerical representation of k/d
        kda = kda.split("/")
        deaths = int(kda[1])
        self._kills = int(kda[0])
        self._deaths = deaths
        self._assists = int(kda[2])

        total_kills += self._kills
        total_deaths += self._deaths
        self._total_kills = total_kills
        self._total_deaths = total_deaths

        if deaths == 0:  # avoid divide by 0
            deaths = 0.5
        self._kda_numerical = self._kills / deaths

        # calculating numerical representation of rating
        rating = rating.split("/")
        self._rating_numerical = float(rating[0])

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
        if attribute == "time":
            return self._time
        if attribute == "duration":
            return self._duration
        if attribute == "rating":
            return self._rating
        if attribute == "kills":
            return self._kills
        if attribute == "deaths":
            return self._deaths
        if attribute == "assists":
            return self._assists
        if attribute == "games":
            return self._game_count
        if attribute == "total_kills":
            return self._total_kills
        if attribute == "total_deaths":
            return self._total_deaths
        if attribute == "map":
            return self._map

    def get_numeric_attr(self, attribute: str):
        """
        This returns only numerical representations of the data saved, so we can graph it.
        There are some special ones that we need to check first. kda, time, and rating should be the decimal version,
        not the fractional version
        :param attribute: string of attribute name we want
        :return: numeric value of attribute, so we can graph it
        """
        # quick check to see if its one of the special data types that needs a different numerical type
        if attribute == "kda":
            return self._kda_numerical
        if attribute == "time":
            return self._center_time
        if attribute == "rating":
            return self._rating_numerical
        return self.get_attr(attribute)

    def csv_repr(self) -> list:
        return [self._kda, self._acs, self._rr, self._time, self._rating, self._duration, self._game_count, self._map]


@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))


@client.event
async def on_message(message):
    if message.author == client.user or not message.content.startswith(prefix):
        return

    msg = message.content[len(prefix):].strip().lower()

    if msg.startswith("hello"):
        await message.channel.send('Ian you suck but please dont ban me')

    if msg.startswith("wakka"):
        await message.channel.send("<:wakkawakka:968379435231379536>")
        await message.channel.send("https://tenor.com/view/pacman-video-game-eating-marshmallow-gif-6008098")

    if msg.startswith("template"):
        # send a template so noah can easily copy paste and not have any errors
        await message.channel.send("v! log kda=*K*/*D*/*A* rr=*RANK_RR* acs=*ACS* map=*MAP* time=*HH*:*MM*-*HH*:*MM* "
                                   "rating=*XX.XX*/11\n(NOTE! these can be done out of order!) example:\n"
                                   "`v! log kda=12/8/6 rr=s2_34 acs=122 map=icebox time=10:45-11:13 rating=8.25/11`")

    if msg.startswith("help"):
        await message.channel.send("Hello there! Firstly, here are the valid commands:\n"
                                   "v! help - gives you this help message\n\n"
                                   "v! hello - a ping command to make sure the bot is working\n\n"
                                   "v! wakka - sends wakka emoji and gif\n\n"
                                   "v! template - sends the template message for logging data\n\n"
                                   "v! log - (Noah and Bennett only) adds the data of a new game to our tracking "
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
        await send_graph(message, "time", "rr", "plot")
        await send_graph(message, "games", "rr", "step")
        await send_graph(message, "time", "acs", "scatter")
        await send_graph(message, "time", "kda", "scatter")
        await send_graph(message, "time", "rating", "plot")
        await send_graph(message, "games", "total_kills", "plot")
    elif msg.startswith("graph"):
        msg = msg[5:].strip().split()

        graph_type = "plot"
        if len(msg) > 1:
            graph_type = msg[0]
            msg = msg[1].strip()

            if graph_type == "pie" or graph_type == "histogram":
                await send_graph(message, msg, "time", graph_type)  # we ignore this time data
                return
        else:
            msg = msg[0]

        axes = msg.split("/")
        x_axis = axes[1]
        y_axis = axes[0]
        await send_graph(message, x_axis, y_axis, graph_type)


    if msg.startswith("log") and (message.author.id == 290691954696781835 or message.author.id == 315699111162675200):
        # only noah or I can enter data
        try:
            msg_split = msg[3:].split()  # [3:] to remove "log"
            new_game_data = {"kda": None, "acs": None, "rr": None, "time": None, "rating": None, "map": None}

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

            starting_min = minutes_since_start(new_game_data['time'].split('-')[0])
            if starting_min < latest_time:
                await message.channel.send("invalid time")
                return

            game = ValorantGame(new_game_data["kda"], new_game_data["acs"], new_game_data["rr"],
                                new_game_data["time"], new_game_data["rating"], new_game_data["map"])
            data.append(game)
            await save_data(game)
            await message.channel.send("successfully added the data")

        except Exception as e:
            await message.channel.send(f"{message.author.mention}! There was an error entering the data, try again. "
                                       f"Or maybe something is broken (oh no!)")
            await message.channel.send(e)
            print(e)
            traceback.print_exc()


def minutes_since_start(time: str) -> int:
    """
    This calculates the number of minutes between the given time and 4am (the starting time)
    4am is declared as time 0, and all time after that is just hours and mins since then
    :param time: this is time in the format of H:M
    :return:
    """
    time = time.split(":")
    hours = int(time[0])
    mins = int(time[1])
    return mins + 60 * hours


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


async def save_data(game: ValorantGame) -> None:
    """
    This saves the newly created game
    :param game: valorant game which holds all needed csv data
    :return: Nothing, this saves to a file
    """
    with open(save_file, 'a') as file:
        writer = csv.writer(file)
        writer.writerow(game.csv_repr())


def create_data():
    """
    This reads previous game data into a csv in case the bot crashes.
    :return: None, but the data will be saved in the global data variable
    """
    global data

    try:
        with open(save_file, 'r') as file:
            reader = csv.reader(file)
            next(reader)  # skip the field names

            for row in reader:
                data.append(ValorantGame(row[0], row[1], int(row[2]), row[3], row[4], row[-1]))

    except FileNotFoundError:
        with open(save_file, 'w') as file:
            writer = csv.writer(file)
            writer.writerow(["kda", "acs", "rr", "time", "rating", "duration", "game_counter", "map"])


async def send_graph(message, x_axis_name: str, y_axis_name: str, graph_type) -> None:
    """
    This creates a graph and then sends it in discord
    :param message: discord message to we can send the file
    :param x_axis_name: x-axis name
    :param y_axis_name: y-axis name
    :param x_data: x data points
    :param y_data: y data points
    :param graph_type: the type, default is plot, but it can be scatter
    :return: None, instead we send a graph in discord
    """
    await create_graph(x_axis_name, y_axis_name, graph_type)
    await message.channel.send("", file=discord.File(graph_image))


async def create_graph(x_axis_name: str, y_axis_name: str, graph_type) -> None:
    """
    This creates the graph and saves it to a file to send
    :param x_axis_name: x-axis name
    :param y_axis_name: y-axis name
    :param x_data: x data points
    :param y_data: y data points
    :param graph_type: the type, default is plot, but it can be scatter
    :return: None, instead we send a graph in discord
    """
    if os.path.exists(graph_image):
        os.remove(graph_image)

    x_data = [game.get_numeric_attr(x_axis_name) for game in data]
    y_data = [game.get_numeric_attr(y_axis_name) for game in data]

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


def main() -> None:
    create_data()
    client.run(DC_TOKEN)


if __name__ == '__main__':
    main()
