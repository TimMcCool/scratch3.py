from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket
from threading import Thread
from ..utils import exceptions
import json
import time
from ..site import user, cloud_activity
from ._base import BaseEventHandler

class TwCloudSocket(WebSocket):

    def handleMessage(self):
        if not self.server.running:
            return
        try:
            if self.server.check_for_ip_ban(self):
                return
            
            data = json.loads(self.data)

            if data["method"] == "set":
                # cloud variable set received
                print(self.address[0]+":"+str(self.address[1]), f"set {data['name']} to {data['value']}, project:", str(data["project_id"]), "user:",data["user"])
                self.server.set_var(data["project_id"], data["name"], data["value"])
                # check if project_id is in whitelisted projects (if there's a list of whitelisted projects)
                if self.server.whitelisted_projects is not None:
                    if data["project_id"] not in self.server.whitelisted_projects:
                        self.close()
                        print(self.address[0]+":"+str(self.address[1]), "tried to handshake on non-whitelisted project and was disconnected, project:", data["project_id"], "user:",data["user"])
                # check if value is valid
                if not self.server._check_value(data["value"]):
                    print(self.address[0]+":"+str(self.address[1]), "sent an invalid var value")
                    return
                # forward to other users connected to the same project
                send_to_clients = {
                    "method" : "set", "user" : data["user"], "project_id" : data["project_id"], "name" : data["name"],
                    "value" : data["value"], "timestamp" : round(time.time() * 1000), "server" : "scratchattach/2.0.0",
                }
                for user in self.server.active_user_ips(data["project_id"]):
                    ud = self.server.tw_clients[user]
                    if ud["client"] == self:
                        continue # don't forward to the sender theirself
                    ud["client"].sendMessage(json.dumps(send_to_clients))
                # raise event
                _a = cloud_activity.CloudActivity(timestamp=time.time()*1000)
                data["name"] = data["name"].replace("☁ ", "")
                _a._update_from_dict(send_to_clients)
                Thread(target=self.server.call_event, args=["on_set", _a, self])

            elif data["method"] == "handshake":
                data = json.loads(self.data)
                # check if handshake is valid
                if not "user" in data:
                    print("Error:", self.address[0]+":"+str(self.address[1]), "handshake without providing a username")
                    return
                if not "project_id" in data:
                    print("Error:", self.address[0]+":"+str(self.address[1]), "handshake without providing a project_id")
                    return
                # check if project_id is in username is allowed
                if self.server.allow_nonscratch_names is False:
                    if not user.get_user(self.data["user"]).does_exist():
                        self.close()
                        print(self.address[0]+":"+str(self.address[1]), "tried to handshake using a username not existing on Scratch, project:", data["project_id"], "user:",data["user"])
                # check if project_id is in whitelisted projects (if there's a list of whitelisted projects)
                if self.server.whitelisted_projects is not None:
                    if data["project_id"] not in self.server.whitelisted_projects:
                        self.close()
                        print(self.address[0]+":"+str(self.address[1]), "tried to handshake on non-whitelisted project and was disconnected, project:", data["project_id"], "user:",data["user"])
                # register handshake in users list (save username and project_id)
                print(self.address[0]+":"+str(self.address[1]), "handshaked, project:", data["project_id"], "user:",data["user"])
                self.server.tw_clients[self.address]["username"] = data["user"]
                self.server.tw_clients[self.address]["project_id"] = data["project_id"]
                # send current cloud variable values to the user who handshaked
                self.sendMessage("\n".join([
                    json.dumps({
                        "method" : "set", "project_id" : data["project_id"], "name" : "☁ "+varname,
                        "value" : self.server.tw_variables[str(data["project_id"])][varname], "server" : "scratchattach/2.0.0",
                    }) for varname in self.server.get_project_vars(str(data["project_id"]))])
                )
                # raise event
                Thread(target=self.server.call_event, args=["on_handshake", self.address, data["user"], data["project_id"], self])

            else:
                print("Error:", self.address[0]+":"+str(self.address[1]), "sent a message without providing a valid method (set, handshake)")

        except Exception as e:
            print("Internal error in handleMessage:", e)

    def handleConnected(self):
        if not self.server.running:
            return
        try:
            if self.server.check_for_ip_ban(self):
                return

            print(self.address[0]+":"+str(self.address[1]), "connected")
            self.server.tw_clients[self.address] = {"client":self, "username":None, "project_id":None}
            # raise event
            Thread(target=self.server.call_event, args=["on_connect", self.address, self])
        except Exception as e:
            print("Internal error in handleConntected:", e)

    def handleClose(self):
        if not self.server.running:
            return
        try:
            if self.address in self.server.tw_clients:
                # raise event
                Thread(target=self.server.call_event, args=["on_disconnect", self.address, self.server.tw_clients[self.address]["username"], self.server.tw_clients[self.address]["project_id"], self])
                print(self.address[0]+":"+str(self.address[1]), "disconnected")
        except Exception as e:
            print("Internal error in handleClose:", e)

def start_tw_cloud_server(hostname='127.0.0.1', port=8080, *, thread=True, length_limit=None, allow_non_numeric=True, whitelisted_projects=None, allow_nonscratch_names=True, blocked_ips=[]):
    """
    Starts a websocket server which can be used with TurboWarp's ?cloud_host URL parameter.
    
    Prints out the websocket address in the console.
    """
    print(f"Serving websocket server: ws://{hostname}:{port}")

    class TwCloudServer(SimpleWebSocketServer, BaseEventHandler):
        def __init__(self, hostname, *, port, websocketclass):
            super().__init__(hostname, port=port, websocketclass=websocketclass)
            self.running = True
            self.tw_clients = {}
            self.tw_variables = {}  # Holds cloud variable states
            self.allow_non_numeric = allow_non_numeric
            self.whitelisted_projects = whitelisted_projects
            self.length_limit = length_limit
            self.allow_nonscratch_names = allow_nonscratch_names
            self.blocked_ips = blocked_ips

        def check_for_ip_ban(self, client):
            if client.address[0] in self.blocked_ips or client.address[0]+":"+str(client.address[1]) in self.blocked_ips or client.address in self.blocked_ips:
                client.sendMessage("You have been banned from this server")
                client.close()
                print(client.address[0]+":"+str(client.address[1]), "(IP-banned) was disconnected")
                return True
            return False
                            
        def active_projects(self):
            only_active = {}
            for project_id in self.tw_variables:
                if self.active_user_ips(project_id) != []:
                    only_active[project_id] = self.tw_variables[project_id]
            return only_active

        def active_user_names(self, project_id):
            return [self.tw_clients[user]["username"] for user in self.active_user_ips(project_id)]

        def active_user_ips(self, project_id):
            return list(filter(lambda user : str(self.tw_clients[user]["project_id"]) == str(project_id), self.tw_clients))

        def get_global_vars(self):
            return self.tw_variables

        def get_project_vars(self, project_id):
            project_id = str(project_id)
            if project_id in self.tw_variables:
                return self.tw_variables[project_id]
            else: return {}
        
        def get_var(self, project_id, var_name):
            project_id = str(project_id)
            var_name = var_name.replace("☁ ", "")
            if project_id in self.tw_variables:
                if var_name in self.tw_variables[project_id]:
                    return self.tw_variables[project_id][var_name]
                else: return None
            else: return None
        
        def set_global_vars(self, data):
            for project_id in data:
                self.set_project_vars(project_id, data[project_id])

        def set_project_vars(self, project_id, data):
            project_id = str(project_id)
            self.tw_variables[project_id] = data
            for client in [self.tw_clients[ip]["client"] for ip in self.active_user_ips(project_id)]:
                client.sendMessage("\n".join([
                    json.dumps({
                        "method" : "set", "project_id" : project_id, "name" : "☁ "+varname,
                        "value" : data[varname], "server" : "scratchattach/2.0.0",
                    }) for varname in data])
                )

        def set_var(self, project_id, var_name, value):
            var_name = var_name.replace("☁ ", "")
            project_id = str(project_id)
            if project_id not in self.tw_variables:
                self.tw_variables[project_id] = {}               
            self.tw_variables[project_id][var_name] = value

            for client in [self.tw_clients[ip]["client"] for ip in self.active_user_ips(project_id)]:
                client.sendMessage(
                    json.dumps({
                        "method" : "set", "project_id" : project_id, "name" : "☁ "+var_name,
                        "value" : value, "server" : "scratchattach/2.0.0",
                    })
                )

        def _check_value(self, value):
            # Checks if a received cloud value satisfies the server's constraints
            if self.length_limit is not None:
                if str(value) > self.length_limit:
                    return False
            if self.allow_non_numeric is False:
                x = value.replace(".", "")
                x = x.replace("-", "")
                if not (x.isnumeric() or x == ""):
                    return False
            return True

        def start(self):
            # overrides start function from BaseEventHandler which is not needed here
            print("The server is already running")
        
        def _update(self):
            # overrides start function from BaseEventHandler which is not needed here
            return

        def pause(self):
            self.running = False

        def resume(self):
            self.running = True

        def stop(self):
            self.running = False
            self.close()

    try:
        server = TwCloudServer(hostname, port=port, websocketclass=TwCloudSocket)
        if thread:
            Thread(target=server.serveforever).start()
            return server
        else:
            server.serveforever()
    except Exception as e:
        raise exceptions.WebsocketServerError(str(e))
    