import spindrift.http as http
import spindrift.network as network

'''
    connect to google using http to handle the connection
'''


class Google(http.HTTPHandler):

    def on_ready(self):
        self.send()  # GET /

    def on_http_data(self):  # we're done reading all the response; print and close
        self.http_content = self.http_content.replace('\xa0', '&nbsp')  # unfortunate
        print(self.http_content)
        self.close('done')

    def on_close(self, reason):
        print('close', reason)


n = network.Network()
c = n.add_connection('www.google.com', 80, Google)
while c.is_open:  # much cleaner way of knowing we're done than google.py
    n.service()
