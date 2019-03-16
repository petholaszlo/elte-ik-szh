import select
import socket
import sys
import Queue

class ChatServer:
  def __init__(self, addr='localhost', port=10001, timeout=1): # timeout: opcionalis parameter, ha nem adjuk meg akk ez a kezdoertek
    self.server, self.message_queues = self.setupServer(addr, port)
    self.inputs = [ self.server ] # Sockets from which we expect to read
    # Sockets to which we expect to write
    self.outputs = []
    self.username = {}
    self.timeout=timeout # Wait for at least one of the sockets to be ready for processing

  def setupServer(self, addr, port):
    # Create a TCP/IP socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setblocking(0)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Bind the socket to the port
    server_address = (addr, port)
    server.bind(server_address)

    # Listen for incoming connections
    server.listen(5)

    # Outgoing message queues ([username]:...)
    message_queues = Queue.Queue()
    return server, message_queues

  def handleNewConnection(self, sock):
    # A "readable" server socket is ready to accept a connection
    connection, client_address = sock.accept()
    connection.setblocking(0)	# or connection.settimeout(1.0)
    name = connection.recv(20)
    print >>sys.stderr, 'new connection from', client_address, "with username", name
    self.username[connection] = name.strip()
    self.message_queues.put("["+self.username[connection]+"] is LOGIN")
    
    self.inputs.append(connection)
    self.outputs.append(connection)

  def handleSocketError(self, err, sock, writable):
    errorcode=err[0]
    if errorcode == 10054: # WSAECONNRESET
        print >>sys.stderr, 'The connection was forcibly closed by', sock.getpeername()
        # Stop listening for input on the connection
        if sock in self.outputs:
            self.outputs.remove(sock)
        self.inputs.remove(sock)
        writable.remove(sock)
        self.message_queues.put("["+self.username[sock]+"] is LOGOUT")
    else:
        raise # Re-throwing exception

  def handleDataFromClient(self, sock, writable):
    try:
        data = sock.recv(1024)
    except socket.error as err:
        self.handleSocketError(err, sock, writable)
    else:
        data = data.strip()
        if data:
            # A readable client socket has data
            print >>sys.stderr, 'received "%s" from %s' % (data, sock.getpeername())
            self.message_queues.put("["+self.username[sock]+"]: "+data)
        else:
            print >>sys.stderr, 'closing', sock.getpeername(), 'after reading no data' # Interpret empty result as closed connection
            if sock in self.outputs: # Stop listening for input on the connection
                self.outputs.remove(sock)
            self.inputs.remove(sock)
            writable.remove(sock)
            sock.close()
            self.message_queues.put("["+self.username[sock]+"] is LOGOUT")

  def handleInputs(self, readable, writable):
    for sock in readable:
        if sock is self.server:
            self.handleNewConnection(sock)
        else:
            self.handleDataFromClient(sock, writable)

  def handleOutputs(self, writable):
    while not self.message_queues.empty():
      try:
          next_msg = self.message_queues.get_nowait()
          print next_msg
      except Queue.Empty:
          break
      else:
          for sock in writable:
              print >>sys.stderr, 'sending "%s" to %s' % (next_msg, sock.getpeername())
              sock.send(next_msg)

  def handleExceptionalCondition(self, exceptional):
    for sock in exceptional:
      print >>sys.stderr, 'handling exceptional condition for', sock.getpeername()
      self.inputs.remove(sock) # Stop listening for input on the connection
      if sock in self.outputs:
          self.outputs.remove(sock)
      sock.close()

  def handleConnections(self):
    while self.inputs:
      try:
        readable, writable, exceptional = select.select(self.inputs, self.outputs, self.inputs, self.timeout)

        if not (readable or writable or exceptional):
            #print >>sys.stderr, '  timed out, do some other work here'
            continue

        self.handleInputs(readable, writable)
        self.handleOutputs(writable)
        self.handleExceptionalCondition(exceptional)
      except KeyboardInterrupt:
        print "Close the system"
        for c in self.inputs:
            c.close()
        self.inputs = []

chatServer = ChatServer()
chatServer.handleConnections()