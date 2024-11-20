from django.urls import path
from django_sockets.middleware import AuthMiddlewareStack
from django_sockets.sockets import BaseSocketServer
from django_sockets.utils import URLRouter

    
class SocketServer(BaseSocketServer):
    def configure(self):
        '''
        This method is optional and only needs to be defined 
        if you are broadcasting or subscribing to channels.

        It is not required if you just plan to respond to
        individual websocket clients.

        This method is used during the initialization of the
        socket server to define the cache hosts that will be
        used for broadcasting and subscribing to channels.
        '''
        self.hosts = [{"address": "redis://0.0.0.0:6379"}]

    def connect(self):
        '''
        This method is optional and is called when a websocket
        client connects to the server. 
        
        It can be used for a variety of purposes such as 
        subscribing to a channel.
        '''
        # When a client connects, create a channel_id attribute 
        # that is set to the user's id. This allows for user scoped 
        # channels if you are using the AuthMiddlewareStack.
        # Note: Since we are not using authentication, all 
        # clients will be subscribed to the same channel ('None').
        self.channel_id = str(self.scope['user'].id)
        self.subscribe(self.channel_id)

    def receive(self, data):
        '''
        This method is called when a websocket client sends
        data to the server. It can be used to:
            - Execute Custom Logic
            - Update the state of the server
            - Send data back to the client
            - Subscribe to a channel
            - Broadcast data to be sent to subscribed clients
        '''
        if data.get('command')=='reset':
            data['counter']=0
        elif data.get('command')=='increment':
            data['counter']+=1
        else:
            raise ValueError("Invalid command")
        # Broadcast the update to all websocket clients 
        # subscribed to this socket's channel_id
        self.broadcast(self.channel_id, data)
        # Alternatively if you just want to respond to the 
        # current socket client, just use self.send(data):
        # self.send(data)


def get_ws_asgi_application():
    '''
    Define the websocket routes for the Django application.

    You can have multiple websocket routes defined here.

    This is the place to apply any needed middleware.
    '''
    # Note: `AuthMiddlewareStack` is not required, but is useful 
    # for user scoped channels.
    return AuthMiddlewareStack(URLRouter([
        path("ws/", SocketServer.as_asgi),
    ]))