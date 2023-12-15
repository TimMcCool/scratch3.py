from .cloud import *
from .user import *
from .session import *
from .project import *
from .studio import *
from .cloud_requests import *
from .forum import *
from .encoder import *

def get_news(*, limit=10, offset=0):
    return requests.get(f"https://api.scratch.mit.edu/news?limit={limit}&offset={offset}").json()

def featured_projects(json=False):
    response = requests.get("https://api.scratch.mit.edu/proxy/featured").json()["community_featured_projects"]
    if json:
        return response
    return [Project(**project) for project in response]

def featured_studios(json=False):
    response = requests.get("https://api.scratch.mit.edu/proxy/featured").json()["community_featured_studios"]
    if json:
        return response
    return [Studio(**studio) for studio in response]

def top_loved(json=False):
    response = requests.get("https://api.scratch.mit.edu/proxy/featured").json()["community_most_loved_projects"]
    if json:
        return response
    return [Project(**project) for project in response]

def top_remixed(json=False):
    response = requests.get("https://api.scratch.mit.edu/proxy/featured").json()["community_most_remixed_projects"]
    if json:
        return response
    return [Project(**project) for project in response]

def newest_projects(json=False):
    response = requests.get("https://api.scratch.mit.edu/proxy/featured").json()["community_newest_projects"]
    if json:
        return response
    return [Project(**project) for project in response]

def curated_projects(json=False):
    response = requests.get("https://api.scratch.mit.edu/proxy/featured").json()["curator_top_projects"]
    return [Project(**project) for project in response]

def design_studio_projects(json=False):
    response = requests.get("https://api.scratch.mit.edu/proxy/featured").json()["scratch_design_studio"]
    if json:
        return response
    return [Project(**project) for project in response]

def search_posts(*, query, order="newest", page=0):
    try:
        data = requests.get(f"https://scratchdb.lefty.one/v3/forum/search?q={query}&o={order}&page={page}").json()["posts"]
        return_data = []
        for o in data:
            a = forum.ForumPost(id = o["id"])
            a._update_from_dict(o)
            return_data.append(a)
        return return_data
    except Exception:
        return []

def total_site_stats():
    data = requests.get("https://scratch.mit.edu/statistics/data/daily/").json()
    data.pop("_TS")
    return data

def monthly_site_traffic():
    data = requests.get("https://scratch.mit.edu/statistics/data/monthly-ga/").json()
    data.pop("_TS")
    return data

def country_counts():
    return requests.get("https://scratch.mit.edu/statistics/data/monthly/").json()["country_distribution"]

def age_distribution():
    data = requests.get("https://scratch.mit.edu/statistics/data/monthly/").json()["age_distribution_data"][0]["values"]
    return_data = {}
    for value in data:
        return_data[value["x"]] = value["y"]
    return return_data

def get_health():
    return requests.get("https://api.scratch.mit.edu/health").json()

def get_csrf_token():
    """
    Generates a scratchcsrftoken using Scratch's API.

    Returns:
        str: The generated scratchcsrftoken
    """
    return requests.get(
        "https://scratch.mit.edu/csrf_token/"
    ).headers["set-cookie"].split(";")[3][len(" Path=/, scratchcsrftoken="):]
