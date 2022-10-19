from twisted.internet import reactor, defer, task


class tests:
    def getDummyData(self, x):
        """
        This function is a dummy which simulates a delayed result and
        returns a Deferred which will fire with that result. Don't try too
        hard to understand this.
        """
        d = defer.Deferred()
        # simulate a delayed result by asking the reactor to fire the
        # Deferred in 2 seconds time with the result x * 3
        reactor.callLater(2, d.callback, 0)
        return d

    def printData(self, data):
        """
        Data handling function to be added as a callback: handles the
        data by printing the result
        """
        # data.addCallback(salut, data)
        print(data)
        # print("FINISHED PROGRAM")

# start up the Twisted reactor (event loop handler) manually
# reactor.run()

def main(reactor):
    d = getDummyData(3)
    d.addCallback(printData)

    # d.callback(3)
    # manually set up the end of the process by asking the reactor to
    # stop itself in 4 seconds time
    # reactor.callLater(4, reactor.stop)
    # d2 = defer.Deferred()
    # d2.addCallback()
    return d

task.react(main)
