"""User class"""
from __future__ import annotations

import json
import random
import string

from ..eventhandlers import message_events
from . import project
from ..utils import exceptions
from . import studio
from . import forum
from bs4 import BeautifulSoup
from ._base import BaseSiteComponent
from ..utils.commons import headers
from ..utils import commons
from . import comment
from . import activity

from ..utils.requests import Requests as requests

class User(BaseSiteComponent):

    '''
    Represents a Scratch user.

    Attributes:

    :.join_date:

    :.about_me:

    :.wiwo: Returns the user's 'What I'm working on' section

    :.country: Returns the country from the user profile

    :.icon_url: Returns the link to the user's pfp (90x90)

    :.id: Returns the id of the user

    :.scratchteam: Retuns True if the user is in the Scratch team

    :.update(): Updates the attributes
    '''

    def __str__(self):
        return str(self.username)

    def __init__(self, **entries):

        # Info on how the .update method has to fetch the data:
        self.update_function = requests.get
        self.update_API = f"https://api.scratch.mit.edu/users/{entries['username']}"

        # Set attributes every User object needs to have:
        self._session = None
        self.id = None
        self.username = None
        self.name = None

        # Update attributes from entries dict:
        entries.setdefault("name", entries.get("username"))
        self.__dict__.update(entries)

        # Set alternative attributes:
        if hasattr(self, "bio"):
            self.about_me = self.bio
        if hasattr(self, "status"):
            self.wiwo = self.status
        if hasattr(self, "name"):
            self.username = self.name

        # Headers and cookies:
        if self._session is None:
            self._headers :dict = headers
            self._cookies = {}
        else:
            self._headers :dict = self._session._headers
            self._cookies = self._session._cookies

        # Headers for operations that require accept and Content-Type fields:
        self._json_headers = dict(self._headers)
        self._json_headers["accept"] = "application/json"
        self._json_headers["Content-Type"] = "application/json"

    def _update_from_dict(self, data):
        try: self.id = data["id"]
        except KeyError: pass
        try: self.username = data["username"]
        except KeyError: pass
        try: self.scratchteam = data["scratchteam"]
        except KeyError: pass
        try: self.join_date = data["history"]["joined"]
        except KeyError: pass
        try: self.about_me = data["profile"]["bio"]
        except KeyError: pass
        try: self.wiwo = data["profile"]["status"]
        except KeyError: pass
        try: self.country = data["profile"]["country"]
        except KeyError: pass
        try: self.icon_url = data["profile"]["images"]["90x90"]
        except KeyError: pass
        return True

    def _assert_permission(self):
        self._assert_auth()
        if self._session._username != self.username:
            raise exceptions.Unauthorized(
                "You need to be authenticated as the profile owner to do this.")

    def does_exist(self):
        """
        Returns:
            boolean : True if the user exists, False if the user is deleted, None if an error occured
        """
        status_code = requests.get(f"https://scratch.mit.edu/users/{self.username}/").status_code
        if status_code == 200:
            return True
        elif status_code == 404:
            return False

    def is_new_scratcher(self):
        """
        Returns:
            boolean : True if the user has the New Scratcher status, else False
        """
        try:
            res = requests.get(f"https://scratch.mit.edu/users/{self.username}/").text
            group=res[res.rindex('<span class="group">'):][:70]
            return "new scratcher" in group.lower()
        except Exception:
            return None

    def message_count(self):

        return json.loads(requests.get(f"https://api.scratch.mit.edu/users/{self.username}/messages/count/?cachebust={random.randint(0,10000)}", headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.3c6 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36',}).text)["count"]

    def featured_data(self):
        """
        Returns:
            dict: Gets info on the user's featured project and featured label (like "Featured project", "My favorite things", etc.)
        """
        try:
            response = json.loads(requests.get(f"https://scratch.mit.edu/site-api/users/all/{self.username}/").text)
            return {
                "label":response["featured_project_label_name"],
                "project":
                        dict(
                            id=str(response["featured_project_data"]["id"]),
                            author=response["featured_project_data"]["creator"],
                            thumbnail_url="https://"+response["featured_project_data"]["thumbnail_url"][2:],
                            title=response["featured_project_data"]["title"]
                        )
                    }
        except Exception:
            return None

    def follower_count(self):
        # follower count
        text = requests.get(
            f"https://scratch.mit.edu/users/{self.username}/followers/",
            headers = self._headers
        ).text
        return commons.webscrape_count(text, "Followers (", ")")

    def following_count(self):
        # following count
        text = requests.get(
            f"https://scratch.mit.edu/users/{self.username}/following/",
            headers = self._headers
        ).text
        return commons.webscrape_count(text, "Following (", ")")

    def followers(self, *, limit=40, offset=0):
        """
        Returns:
            list<scratchattach.user.User>: The user's followers as list of scratchattach.user.User objects
        """
        response = commons.api_iterative(
            f"https://api.scratch.mit.edu/users/{self.username}/followers/", limit=limit, offset=offset)
        return commons.parse_object_list(response, User, self._session, "username")

    def follower_names(self, *, limit=40, offset=0):
        """
        Returns:
            list<str>: The usernames of the user's followers
        """
        return [i.name for i in self.followers(limit=limit, offset=offset)]

    def following(self, *, limit=40, offset=0):
        """
        Returns:
            list<scratchattach.user.User>: The users that the user is following as list of scratchattach.user.User objects
        """
        response = commons.api_iterative(
            f"https://api.scratch.mit.edu/users/{self.username}/following/", limit=limit, offset=offset)
        return commons.parse_object_list(response, User, self._session, "username")

    def following_names(self, *, limit=40, offset=0):
        """
        Returns:
            list<str>: The usernames of the users the user is following
        """
        return [i.name for i in self.following(limit=limit, offset=offset)]

    def is_following(self, user):
        """
        Returns:
            boolean: Whether the user is following the user provided as argument
        """
        offset = 0
        following = False

        while True:
            try:
                following_names = self.following_names(limit=20, offset=offset)
                if user in following_names:
                    following = True
                    break
                if following_names == []:
                    break
                offset += 20
            except Exception:
                print("Warning: API error when performing following check")
                return following
        return following

    def is_followed_by(self, user):
        """
        Returns:
            boolean: Whether the user is followed by the user provided as argument
        """
        return User(username=user).is_following(self.username)

    def project_count(self):
        text = requests.get(
            f"https://scratch.mit.edu/users/{self.username}/projects/",
            headers = self._headers
        ).text
        return commons.webscrape_count(text, "Shared Projects (", ")")

    def studio_count(self):
        text = requests.get(
            f"https://scratch.mit.edu/users/{self.username}/studios/",
            headers = self._headers
        ).text
        return commons.webscrape_count(text, "Studios I Curate (", ")")

    def studios_following_count(self):
        text = requests.get(
            f"https://scratch.mit.edu/users/{self.username}/studios/",
            headers = self._headers
        ).text
        return commons.webscrape_count(text, "Studios I Follow (", ")")

    def studios(self, *, limit=40, offset=0):
        _studios = commons.api_iterative(
            f"https://api.scratch.mit.edu/users/{self.username}/studios/curate", limit=limit, offset=offset)
        studios = []
        for studio_dict in _studios:
            _studio = studio.Studio(_session = self._session, id = studio_dict["id"])
            _studio._update_from_dict(studio_dict)
            studios.append(_studio)
        return studios

    def projects(self, *, limit=40, offset=0) -> list[project.Project]:
        """
        Returns:
            list<projects.projects.Project>: The user's shared projects
        """
        _projects = commons.api_iterative(
            f"https://api.scratch.mit.edu/users/{self.username}/projects/", limit=limit, offset=offset, _headers= self._headers)
        for p in _projects:
            p["author"] = {"username":self.username}
        return commons.parse_object_list(_projects, project.Project, self._session)

    def loves(self, *, limit=40, offset=0, get_full_project: bool = False) -> list[project.Project]:
        """
        Returns:
            list<projects.projects.Project>: The user's loved projects
        """
        # We need to use beautifulsoup webscraping so we cant use the api_iterative function
        if offset < 0:
            raise exceptions.BadRequest("offset parameter must be >= 0")
        if limit < 0:
            raise exceptions.BadRequest("limit parameter must be >= 0")

        # There are 40 projects on display per page
        # So the first page you need to view is 1 + offset // 40
        # (You have to add one because the first page is idx 1 instead of 0)

        # The final project to view is at idx offset + limit - 1
        # (You have to -1 because the index starts at 0)
        # So the page number for this is 1 + (offset + limit - 1) // 40

        # But this is a range so we have to add another 1 for the second argument
        pages = range(1 + offset // 40,
                      2 + (offset + limit - 1) // 40)
        _projects = []

        for page in pages:
            # The index of the first project on page #n is just (n-1) * 40
            first_idx = (page - 1) * 40

            page_content = requests.get(f"https://scratch.mit.edu/projects/all/{self.username}/loves/"
                                        f"?page={page}", headers=self._headers).content

            soup = BeautifulSoup(
                page_content,
                "html.parser"
            )

            # We need to check if we are out of bounds
            # If we are, we can jump out early
            # This is detectable if Scratch gives you a '404'

            # We can't just detect if the 404 text is within the whole of the page content
            # because it would break if someone made a project with that name

            # This page only uses <h1> tags for the 404 text, so we can just use a soup for those
            h1_tag = soup.find("h1")
            if h1_tag is not None:
                # Just to confirm that it's a 404, in case I am wrong. It can't hurt
                if "Whoops! Our server is Scratch'ing its head" in h1_tag.text:
                    break

            # Each project element is a list item with the class name 'project thumb item' so we can just use that
            for i, project_element in enumerate(
                    soup.find_all("li", {"class": "project thumb item"})):
                # Remember we only want certain projects:
                # The current project idx = first_idx + i
                # We want to start at {offset} and end at {offset + limit}

                # So the offset <= current project idx <= offset + limit
                if offset <= first_idx + i <= offset + limit:
                    # Each of these elements provides:
                    # A project id
                    # A thumbnail link (no need to webscrape this)
                    # A title
                    # An Author (called an owner for some reason)

                    project_anchors = project_element.find_all("a")
                    # Each list item has three <a> tags, the first two linking the project
                    # 1st contains <img> tag
                    # 2nd contains project title
                    # 3rd links to the author & contains their username

                    # This function is pretty handy!
                    # I'll use it for an id from a string like: /projects/1070616180/
                    project_id = commons.webscrape_count(project_anchors[0].attrs["href"],
                                                         "/projects/", "/")
                    title = project_anchors[1].contents[0]
                    author = project_anchors[2].contents[0]

                    # Instantiating a project with the properties that we know
                    # This may cause issues (see below)
                    _project = project.Project(id=project_id,
                                               _session=self._session,
                                               title=title,
                                               author_name=author,
                                               url=f"https://scratch.mit.edu/projects/{project_id}/")
                    if get_full_project:
                        # Put this under an if statement since making api requests for every single
                        # project will cause the function to take a lot longer
                        _project.update()

                    _projects.append(
                        _project
                    )

        return _projects

    def loves_count(self):
        text = requests.get(
            f"https://scratch.mit.edu/projects/all/{self.username}/loves/",
            headers=self._headers
        ).text

        # If there are no loved projects, then Scratch doesn't actually display the number - so we have to catch this
        soup = BeautifulSoup(text, "html.parser")

        if not soup.find("li", {"class": "project thumb item"}):
            # There are no projects, so there are no projects loved
            return 0

        return commons.webscrape_count(text, "&raquo;\n\n (", ")")

    def favorites(self, *, limit=40, offset=0):
        """
        Returns:
            list<projects.projects.Project>: The user's favorite projects
        """
        _projects = commons.api_iterative(
            f"https://api.scratch.mit.edu/users/{self.username}/favorites/", limit=limit, offset=offset, _headers= self._headers)
        return commons.parse_object_list(_projects, project.Project, self._session)

    def favorites_count(self):
        text = requests.get(
            f"https://scratch.mit.edu/users/{self.username}/favorites/",
            headers = self._headers
        ).text
        return commons.webscrape_count(text, "Favorites (", ")")

    def toggle_commenting(self):
        """
        You can only use this function if this object was created using :meth:`scratchattach.session.Session.connect_user`
        """
        self._assert_permission()
        requests.post(f"https://scratch.mit.edu/site-api/comments/user/{self.username}/toggle-comments/",
            headers = headers,
            cookies = self._cookies
        )

    def viewed_projects(self, limit=24, offset=0):
        """
        Returns:
            list<projects.projects.Project>: The user's recently viewed projects

        You can only use this function if this object was created using :meth:`scratchattach.session.Session.connect_user`
        """
        self._assert_permission()
        _projects = commons.api_iterative(
            f"https://api.scratch.mit.edu/users/{self.username}/projects/recentlyviewed", limit=limit, offset=offset, _headers= self._headers)
        return commons.parse_object_list(_projects, project.Project, self._session)

    def set_pfp(self, image: bytes):
        """
        Sets the user's profile picture. You can only use this function if this object was created using :meth:`scratchattach.session.Session.connect_user`
        """
        # Teachers can set pfp! - Should update this method to check for that
        # self._assert_permission()
        requests.post(
            f"https://scratch.mit.edu/site-api/users/all/{self.username}/",
            headers=self._headers,
            cookies=self._cookies,
            files={"file": image})

    def set_bio(self, text):
        """
        Sets the user's "About me" section. You can only use this function if this object was created using :meth:`scratchattach.session.Session.connect_user`
        """
        # Teachers can set bio! - Should update this method to check for that
        # self._assert_permission()
        requests.put(
            f"https://scratch.mit.edu/site-api/users/all/{self.username}/",
            headers=self._json_headers,
            cookies=self._cookies,
            json={"bio": text})

    def set_wiwo(self, text):
        """
        Sets the user's "What I'm working on" section. You can only use this function if this object was created using :meth:`scratchattach.session.Session.connect_user`
        """
        # Teachers can also change your wiwo
        # self._assert_permission()
        requests.put(
            f"https://scratch.mit.edu/site-api/users/all/{self.username}/",
            headers=self._json_headers,
            cookies=self._cookies,
            json={"status": text})

    def set_featured(self, project_id, *, label=""):
        """
        Sets the user's featured project. You can only use this function if this object was created using :meth:`scratchattach.session.Session.connect_user`

        Args:
            project_id: Project id of the project that should be set as featured

        Keyword Args:
            label: The label that should appear above the featured project on the user's profile (Like "Featured project", "Featured tutorial", "My favorite things", etc.)
        """
        self._assert_permission()
        requests.put(
            f"https://scratch.mit.edu/site-api/users/all/{self.username}/",
            headers=self._json_headers,
            cookies=self._cookies,
            json={"featured_project": int(project_id), "featured_project_label": label}
        )

    def set_forum_signature(self, text):
        """
        Sets the user's discuss forum signature. You can only use this function if this object was created using :meth:`scratchattach.session.Session.connect_user`
        """
        self._assert_permission()
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://scratch.mit.edu',
            'referer': 'https://scratch.mit.edu/discuss/settings/TimMcCool/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        }
        data = {
            'csrfmiddlewaretoken': 'a',
            'signature': text,
            'update': '',
        }
        response = requests.post(f'https://scratch.mit.edu/discuss/settings/{self.username}/', cookies=self._cookies, headers=headers, data=data)

    def post_comment(self, content, *, parent_id="", commentee_id=""):
        """
        Posts a comment on the user's profile. You can only use this function if this object was created using :meth:`scratchattach.session.Session.connect_user`

        Args:
            content: Content of the comment that should be posted

        Keyword Arguments:
            parent_id: ID of the comment you want to reply to. If you don't want to mention a user, don't put the argument.
            commentee_id: ID of the user that will be mentioned in your comment and will receive a message about your comment. If you don't want to mention a user, don't put the argument.

        Returns:
            scratchattach.comment.Comment: An object representing the created comment.
        """
        self._assert_auth()
        data = {
                "commentee_id": commentee_id,
                "content": str(content),
                "parent_id": parent_id,
        }
        r = requests.post(
            f"https://scratch.mit.edu/site-api/comments/user/{self.username}/add/",
            headers=headers,
            cookies=self._cookies,
            data=json.dumps(data),
        )
        if r.status_code != 200:
            if "Looks like we are having issues with our servers!" in r.text:
                raise exceptions.BadRequest("Invalid arguments passed")
            else:
                raise exceptions.CommentPostFailure(r.text)

        try:
            text = r.text
            data = {
                'id': text.split('<div id="comments-')[1].split('" class="comment')[0],
                'author': {"username": text.split('" data-comment-user="')[1].split('"><img class')[0]},
                'content': text.split('<div class="content">')[1].split('"</div>')[0],
                'reply_count': 0,
                'cached_replies': []
            }
            _comment = comment.Comment(source="profile", parent_id=None if parent_id=="" else parent_id, commentee_id=commentee_id, source_id=self.username, id=data["id"], _session = self._session)
            _comment._update_from_dict(data)
            return _comment
        except Exception:
            if '{"error": "isFlood"}' in text:
                raise(exceptions.CommentPostFailure(
                    "You are being rate-limited for running this operation too often. Implement a cooldown of about 10 seconds."))
            else:
                raise(exceptions.FetchError(f"Couldn't parse API response: {r.text!r}"))

    def reply_comment(self, content, *, parent_id, commentee_id=""):
        """
        Replies to a comment given by its id

        Warning:
            Only replies to top-level comments are shown on the Scratch website. Replies to replies are actually replies to the corresponding top-level comment in the API.

            Therefore, parent_id should be the comment id of a top level comment.

        Args:
            content: Content of the comment that should be posted

        Keyword Arguments:
            parent_id: ID of the comment you want to reply to
            commentee_id: ID of the user that will be mentioned in your comment and will receive a message about your comment. If you don't want to mention a user, don't put the argument.
        """
        return self.post_comment(content, parent_id=parent_id, commentee_id=commentee_id)

    def activity(self, *, limit=1000):
        """
        Returns:
            list<scratchattach.Activity>: The user's activity data as parsed list of scratchattach.activity.Activity objects
        """
        soup = BeautifulSoup(requests.get(f"https://scratch.mit.edu/messages/ajax/user-activity/?user={self.username}&max={limit}").text, 'html.parser')

        activities = []
        source = soup.find_all("li")

        for data in source:
            _activity = activity.Activity(_session = self._session, raw=data)
            _activity._update_from_html(data)
            activities.append(_activity)

        return activities


    def activity_html(self, *, limit=1000):
        """
        Returns:
            str: The raw user activity HTML data
        """
        return requests.get(f"https://scratch.mit.edu/messages/ajax/user-activity/?user={self.username}&max={limit}").text


    def follow(self):
        """
        Follows the user represented by the User object. You can only use this function if this object was created using :meth:`scratchattach.session.Session.connect_user`
        """
        self._assert_auth()
        requests.put(
            f"https://scratch.mit.edu/site-api/users/followers/{self.username}/add/?usernames={self._session._username}",
            headers = headers,
            cookies = self._cookies,
        )

    def unfollow(self):
        """
        Unfollows the user represented by the User object. You can only use this function if this object was created using :meth:`scratchattach.session.Session.connect_user`
        """
        self._assert_auth()
        requests.put(
            f"https://scratch.mit.edu/site-api/users/followers/{self.username}/remove/?usernames={self._session._username}",
            headers = headers,
            cookies = self._cookies,
        )

    def delete_comment(self, *, comment_id):
        """
        Deletes a comment by its ID. You can only use this function if this object was created using :meth:`scratchattach.session.Session.connect_user`

        Args:
            comment_id: The id of the comment that should be deleted
        """
        self._assert_permission()
        return requests.post(
            f"https://scratch.mit.edu/site-api/comments/user/{self.username}/del/",
            headers = headers,
            cookies = self._cookies,
            data = json.dumps({"id":str(comment_id)})
        )

    def report_comment(self, *, comment_id):
        """
        Reports a comment by its ID to the Scratch team. You can only use this function if this object was created using :meth:`scratchattach.session.Session.connect_user`

        Args:
            comment_id: The id of the comment that should be reported
        """
        self._assert_auth()
        return requests.post(
            f"https://scratch.mit.edu/site-api/comments/user/{self.username}/rep/",
            headers = headers,
            cookies = self._cookies,
            data = json.dumps({"id":str(comment_id)})
        )

    def comments(self, *, page=1, limit=None):
        """
        Returns the comments posted on the user's profile (with replies).

        Keyword Arguments:
            page: The page of the comments that should be returned.
            limit: Max. amount of returned comments.

        Returns:
            list<scratchattach.comment.Comment>: A list containing the requested comments as Comment objects.
        """
        URL = f"https://scratch.mit.edu/site-api/comments/user/{self.username}/?page={page}"
        DATA = []

        page_contents = requests.get(URL).content

        soup = BeautifulSoup(page_contents, "html.parser")

        _comments = soup.find_all("li", {"class": "top-level-reply"})

        if len(_comments) == 0:
            return None

        for entity in _comments:
            comment_id = entity.find("div", {"class": "comment"})['data-comment-id']
            user = entity.find("a", {"id": "comment-user"})['data-comment-user']
            content = str(entity.find("div", {"class": "content"}).text).strip()
            time = entity.find("span", {"class": "time"})['title']

            main_comment = {
                'id': comment_id,
                'author': {"username":user},
                'content': content,
                'datetime_created': time,
            }
            _comment = comment.Comment(source="profile", source_id=self.username, _session = self._session)
            _comment._update_from_dict(main_comment)

            ALL_REPLIES = []
            replies = entity.find_all("li", {"class": "reply"})
            if len(replies) > 0:
                hasReplies = True
            else:
                hasReplies = False
            for reply in replies:
                r_comment_id = reply.find("div", {"class": "comment"})['data-comment-id']
                r_user = reply.find("a", {"id": "comment-user"})['data-comment-user']
                r_content = str(reply.find("div", {"class": "content"}).text).strip().replace("\n", "").replace(
                    "                    ", " ")
                r_time = reply.find("span", {"class": "time"})['title']
                reply_data = {
                    'id': r_comment_id,
                    'author':{'username': r_user},
                    'content': r_content,
                    'datetime_created': r_time,
                    "parent_id" : comment_id,
                    "cached_parent_comment" : _comment,
                }
                _r_comment = comment.Comment(source="profile", source_id=self.username, _session = self._session, cached_parent_comment=_comment)
                _r_comment._update_from_dict(reply_data)
                ALL_REPLIES.append(_r_comment)

            _comment.reply_count = len(ALL_REPLIES)
            _comment.cached_replies = list(ALL_REPLIES)

            DATA.append(_comment)
        return DATA

    def comment_by_id(self, comment_id) -> comment.Comment:
        """
        Gets a comment on this user's profile by id.

        Warning:
            For comments very far down on the user's profile, this method will take a while to find the comment. Very old comment are deleted from Scratch's database and may not appear.

        Returns:
            scratchattach.comments.Comment: The request comment.
        """

        page = 1
        page_content = self.comments(page=page)
        while page_content != []:
            results = list(filter(lambda x : str(x.id) == str(comment_id), page_content))
            if results == []:
                results = list(filter(lambda x : str(x.id) == str(comment_id), [item for x in page_content for item in x.cached_replies]))
                if results != []:
                    return results[0]
            else:
                return results[0]
            page += 1
            page_content = self.comments(page=page)
        raise exceptions.CommentNotFound()

    def message_events(self):
        return message_events.MessageEvents(self)

    def stats(self):
        """
        Gets information about the user's stats. Fetched from ScratchDB.

        Warning:
            ScratchDB is down indefinitely, therefore this method is deprecated.

        Returns:
            dict: A dict containing the user's stats. If the stats aren't available, all values will be -1.
        """
        print("Warning: ScratchDB is down indefinitely, therefore this method is deprecated.")
        try:
            stats= requests.get(
                f"https://scratchdb.lefty.one/v3/user/info/{self.username}"
            ).json()["statistics"]
            stats.pop("ranks")
        except Exception:
            stats = {"loves":-1,"favorites":-1,"comments":-1,"views":-1,"followers":-1,"following":-1}
        return stats

    def ranks(self):
        """
        Gets information about the user's ranks. Fetched from ScratchDB.

        Warning:
            ScratchDB is down indefinitely, therefore this method is deprecated.

        Returns:
            dict: A dict containing the user's ranks. If the ranks aren't available, all values will be -1.
        """
        print("Warning: ScratchDB is down indefinitely, therefore this method is deprecated.")
        try:
            return requests.get(
                f"https://scratchdb.lefty.one/v3/user/info/{self.username}"
            ).json()["statistics"]["ranks"]
        except Exception:
            return {"country":{"loves":0,"favorites":0,"comments":0,"views":0,"followers":0,"following":0},"loves":0,"favorites":0,"comments":0,"views":0,"followers":0,"following":0}

    def ocular_status(self):
        """
        Gets information about the user's ocular status. Ocular is a website developed by jeffalo: https://ocular.jeffalo.net/

        Returns:
            dict
        """
        return requests.get(f"https://my-ocular.jeffalo.net/api/user/{self.username}").json()

    def verify_identity(self, *, verification_project_id=395330233):
        """
        Can be used in applications to verify a user's identity.

        This function returns a Verifactor object. Attributs of this object:
        :.projecturl: The link to the project where the user has to go to verify
        :.project: The project where the user has to go to verify as scratchattach.Project object
        :.code: The code that the user has to comment

        To check if the user verified successfully, call the .check() function on the returned object.
        It will return True if the user commented the code.
        """

        class Verificator:

            def __init__(self, user):
                self.project = user._make_linked_object("id", verification_project_id, project.Project, exceptions.ProjectNotFound)
                self.projecturl = self.project.url
                self.code = ''.join(random.choices(string.ascii_letters + string.digits, k=130))
                self.username = user.username

            def check(self):
                return list(filter(lambda x : x.author_name == self.username, self.project.comments())) != []

        v = Verificator(self)
        print(f"{self.username} has to go to {v.projecturl} and comment {v.code} to verify their identity")
        return Verificator(self)

# ------ #

def get_user(username) -> User:
    """
    Gets a user without logging in.

    Args:
        username (str): Username of the requested user

    Returns:
        scratchattach.user.User: An object representing the requested user

    Warning:
        Any methods that require authentication (like user.follow) will not work on the returned object.

        If you want to use these, get the user with :meth:`scratchattach.session.Session.connect_user` instead.
    """
    print("Warning: For methods that require authentication, use session.connect_user instead of get_user")
    return commons._get_object("username", username, User, exceptions.UserNotFound)
