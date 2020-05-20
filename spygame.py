import requests
import json
import os
import sys
import webbrowser
import pickle
import argparse
from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import MobileApplicationClient
from time import sleep, time

# API constants
API_URL = "https://api.vk.com/method"
AUTHORIZE_URL = "https://oauth.vk.com/authorize"
REDIRECT_URI = "https://oauth.vk.com/blank.html"
CLIENT_ID = 7238339

# text coloring constants
G = '\033[92m'  # green
Y = '\033[93m'  # yellow
R = '\033[91m'  # red
B = '\033[1m'  # bold
U = '\033[4m'  # underline
END = '\033[0m'  # end of coloring

OUTPUT = "groups.json"
LOG = "log.txt"

RETRY = 3


class APIError(Exception):

    def __init__(self, response):
        if "error" in response:
            self.body = response["error"]
            self.message = response['error']['error_msg']
        if "execute_errors" in response:
            self.message = response["execute_errors"]
            self.body = response
        super().__init__(response)


def authorize(discard_token):
    """
    Either reads a token from a file or calls get_token() to obtain a new one.
    Typically a token expires in 24 hours (86400 s).

    @return: Dictionary of authorization parameters
    """

    clear_screen()

    print(f"{Y}Authorization...\n{END}")
    sleep(0.5)

    try:
        # checks if the token was saved more that 23h 50m ago
        if time() - os.stat("token.dat").st_mtime < 85800:
            with open("token.dat", "rb") as f:
                data = pickle.load(f)
            print(f"{G}AUTHORIZED FROM A SAVED TOKEN{END}")
            sleep(1)

            return {"v": 5.103, "access_token": data}
        else:
            return get_token(discard_token)
    except FileNotFoundError:
        return get_token(discard_token)


def clear_screen():
    """
    Clears console screen and turns on color support (the latter is only for Win).
    """

    if sys.platform == "win32":
        os.system("cls")
        os.system("color")
    elif sys.platform == "linux":
        os.system("printf '\033c'")


def display_title():
    """
    Displays a fancy title screen. :)
    """

    print("\n")
    print("\t\t********************************************************")
    print("\t\t***                    Spy Game                      ***")
    print("\t\t***      Coursework for Netology Python course      ***")
    print("\t\t***               By Roman Vlasenko                  ***")
    print("\t\t********************************************************")

    print(f"\n{U}Goal: Find and print every VK group which member the user is, but his friends are not.{END}\n")


def find_common(user_groups, user_friends, amount):
    """
    For every group from the user groups list, ckecks if any of the user's friends is a member the group.
    If true, appends this group to a list of common groups.

    @param user_groups: List of user groups IDs
    @param user_friends: List of user friends IDs
    @param amount: Amount of friends IDs which will be sent with every request to the API method
    @return: Set of common groups IDs
    """

    common_groups = set()

    for gindex, group in enumerate(user_groups, start=1):
        sleep(0.3)
        # status bar
        processed = 0
        print(f"{B}Group {gindex}/{len(user_groups)}, "
              f"friends processed: {processed}/{len(user_friends)}    {END}", end="\r")

        for friends_chunk in get_chunk(user_friends, amount):
            sleep(0.2)
            # "user_ids" parameters must be a list of comma-separated numbers
            user_ids = ",".join([str(friend) for friend in friends_chunk])
            params = dict(**token, group_id=group, user_ids=user_ids)

            try:
                response = make_request("/groups.isMember", params).json()

                # update status bar
                processed += len(friends_chunk)
                print(f"{B}Group {gindex}/{len(user_groups)}, "
                      f"friends processed: {processed}/{len(user_friends)}    {END}", end="\r")

                if "response" not in response:
                    raise APIError(response)
            except APIError as error:
                print(f"{R}API Error:{END}", error.message)
                log.append(error.body)
            else:
                # if any friend in the chunk is a member, add the group to the set
                # and get to the next chunk of friends
                for response in response["response"]:
                    if response["member"]:
                        common_groups.add(group)
                        break

    return common_groups


def fetch_uncommon_info(uncommon_groups):
    """
    Retrieves information about user groups, which don't have any of the user's friends for a member.

    @param uncommon_groups: A set of groups IDs
    @return: Dictionary containing a name, an ID and a members count for every uncommon group
    """

    groups_info = []

    for gindex, group in enumerate(uncommon_groups, start=1):
        sleep(0.2)
        params = dict(**token, group_id=group, fields="members_count")
        # status bar
        print(f"{B}Groups processed: {gindex}/{len(uncommon_groups)}  {END}", end="\r")

        try:
            response = make_request("/groups.getById", params).json()
            if "response" not in response:
                raise APIError(response)
        except APIError as error:
            print(f"{R}API Error:{END}", error.message)
            log.append(error.body)
        else:
            name, gid, members_count = response["response"][0]["name"], \
                                       response["response"][0]["id"], \
                                       response["response"][0].get("members_count", "Unavailable")

            groups_info.append({"name": name, "gid": gid, "members_count": members_count})

    return groups_info


def fetch_user_info(user):
    """
    Obtains user info: name, id, list of friends and list of groups. Prints out user's name and ID.

    @param user: User ID or a screen name from input
    @return: List of user friends IDs, list of user groups IDs
    """

    code = """
    var user = API.users.get({"user_ids": """+f'"{user}"'+"""});
    var user_id = user[0].id;
    var name = user[0].first_name + " " + user[0].last_name;
    var groups = API.groups.get({"user_id": user_id, "count": 1000}).items;
    var friends = API.friends.get({"user_id": user_id}).items;

    return {"user_name": name, "user_id": user_id, "friends_ids": friends, "groups_ids": groups};"""
    params = dict(**token, code=code)

    # request user info using VKScript code above
    try:
        response = make_request("/execute", params).json()
        if ("execute_errors" in response) or ("response" not in response):
            raise APIError(response)
    except APIError as error:
        print(f"{R}API Error:{END}", error.message)
        log.append(error.body)
        print(f"\n{Y}PROGRAM TERMINATED{END}")
        quit()
    else:
        user_name, user_id, user_friends, user_groups = response["response"].values()

        print(f"{B}Name: {user_name}{END}")
        print(f"{B}ID: {user_id}{END}")
        sleep(2)

        return user_groups, user_friends


def get_chunk(friendlist, amount):
    """
    Splits list of user friends IDs in chunks, each to be sent to groups.isMember method
    by the find_common() function ("user_ids" field).

    @param friendlist: List of friends IDs
    @param amount: Amunt of items the chunk (default 50, could be changed with a command line argument)
    """

    for index in range(0, len(friendlist), amount):
        yield friendlist[index:index + amount]


def get_token(discard_token):
    """
    Establishes an OAuth2 session to retrieve a token for further API requests.
    Saves retrieved token to a file unless a command line argument "--discard_token" is given.

    @return: Dictionary of authorization parameters
    """
    print(f"{B}Authorization required!\nAllow 'Netology Project 1 by Roman Vlasenko' access "
          f"to your VK account\nand copy the contents of the address bar from the opened tab{END}\n")
    sleep(7)
    with OAuth2Session(client=MobileApplicationClient(client_id=CLIENT_ID), redirect_uri=REDIRECT_URI,
                       scope="friends, groups") as vk:
        authorization_url, state = vk.authorization_url(AUTHORIZE_URL)
        webbrowser.open_new_tab(authorization_url)
        vk_response = input(f"{B}Paste the contents of the address bar here:{END}\n").rstrip()
        vk.token_from_fragment(vk_response)

    if not discard_token:
        with open("token.dat", "wb") as f:
            pickle.dump(vk.access_token, f)

    return {"v": 5.103, "access_token": vk.access_token}


def logger(errors):
    """
    Creates a log file at the end of the program.

    @param errors: List of errors catched during the execution of the program
    """

    if len(errors) < 1:
        errors.append("No errors were catched during the execution")

    with open(LOG, "w", encoding="utf-8") as f:
        for errindex, error in enumerate(errors, start=1):
            f.write(f"Entry {errindex}".center(20, "="))
            f.write("\n")
            json.dump(error, f, indent=2, ensure_ascii=False)
            f.write("\n")


def make_request(method, payload):
    """
    Sends a request to the API, raises ReadTimeout if unable to fetch data after 3 attempts.

    @param method: API method
    @param payload: Dictionary of method parameters
    @return: Response object
    """

    retry_counter = 0
    api_response = None

    while api_response is None and (retry_counter < RETRY):
        try:
            if method == "/groups.isMember":
                api_response = requests.post(API_URL + method, data=payload, timeout=(10, 5))
            else:
                api_response = requests.get(API_URL + method, params=payload, timeout=(10, 5))
        except requests.exceptions.ReadTimeout as error:
            print("Server stopped responding. Retry in 3 s...")
            log.append(error.args[0].args[0])
            retry_counter += 1
            sleep(3)

    if api_response is None:
        raise requests.exceptions.ReadTimeout("Unable to retrieve data")

    return api_response


def parse_arguments():
    """
    Parses command line arguments using argparse module.
    @return: Amount of friends IDs which will be sent with every request to the API method in find_common()
    @return: Boolean value to switch off token pickling option in get_token()
    @return: Boolean value to switch on logging option (see logger())
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--chunk_size",
                        help="amount of friends checked for membership with every API request, max. 500",
                        type=int)
    parser.add_argument("-t", "--discard_token",
                        help="don't save the token to a file",
                        action="store_true")
    parser.add_argument("-d", "--debug",
                        help="generate log file at the termination",
                        action="store_true")
    args = parser.parse_args()

    return args.chunk_size, args.discard_token, args.debug


def print_and_write(groups_info):
    """
    Prints out uncommon groups information and writes this data to a JSON file.

    @param groups_info: Dictionary of groups info
    """

    for group in groups_info:
        print(f"{B}Group name: {group['name']}{END}")
        print(f"{B}Group ID: {group['gid']}{END}")
        print(f"{B}Members count: {group['members_count']}{END}\n")
        sleep(0.2)

    with open(OUTPUT, "w", encoding="utf-8") as file:
        json.dump(groups_info, file, indent=2, ensure_ascii=False)


def main(chunk_size):
    # chunk is the amount of IDs sent with every request in find_common()
    if not chunk_size:
        chunk_size = 50

    clear_screen()
    display_title()

    # retrieve user info
    user = input(f"{Y}Enter user ID/screen name (or type q to quit):{END}\n")
    if user == "q":
        quit()
    print(f"\n{Y}Retrieving user info...{END}\n")
    sleep(1)

    user_groups, user_friends = fetch_user_info(user)

    # find common groups
    print(f"\n{Y}Fetching common groups...{END}")
    sleep(2)
    print(f"{B}Status:{END} {Y}In progress{END}\n")
    sleep(1)

    common_groups = find_common(user_groups, user_friends, chunk_size)

    print(f"\n\n{B}Status:{END} {G}Successful{END}\n")
    sleep(2)

    # find uncommon groups
    print(f"{Y}Calculating difference...{END}")
    sleep(1)

    uncommon_groups = set(user_groups) - common_groups

    print(f"{G}UNCOMMON GROUPS FOUND: {len(uncommon_groups)}{END}\n")
    sleep(2)

    # fetch uncommon groups info
    print(f"{Y}Fetching uncommon groups info...{END}")
    sleep(2)
    print(f"{B}Status:{END} {Y}In progress{END}\n")
    sleep(1)

    uncommon_groups_info = fetch_uncommon_info(uncommon_groups)

    print(f"\n\n{B}Status:{END} {G}Successful{END}\n")
    sleep(2)

    # display retrieved info and write it to a JSON file
    print_and_write(uncommon_groups_info)

    print(f"{B}Saved to {os.path.join(os.getcwd(), OUTPUT)}{END}")
    sleep(1)

    print(f"\n{Y}END OF PROGRAM{END}")


if __name__ == '__main__':
    log = []

    chunk, cache, debug = parse_arguments()
    token = authorize(cache)

    try:
        main(chunk)
    finally:
        if debug:
            logger(log)
            print(f"\n{B}Log file has been saved to {os.getcwd()}\\{LOG}{END}")
