# -*- python -*-

#import logging
#logging.basicConfig(level=logging.DEBUG)


class CountException(Exception):
    """
    Raised when there is a problem with counting votes or interpreting
    the results of a count.
    """
    pass

class IncompleteCount(CountException):
    """
    Raised when the requested operation or information is not
    available because the count is not done yet.
    """
    pass

class Abstract:
    """
    Abstract base class for counting methods.  

    Must provide a public results attribute which is the final result
    of the computation.  The format is not prescribed here.

    Must provide a public residue attribute which can be used for
    inspecting the detailed results of the count, e.g. the progress in
    each round for run-offs or multi-round methods.  The format is not
    prescribed here.

    Idealy, it should be possible to computationally prove that the
    result is valid, given the residue.  At the very least, a human
    official familiar with the counting method should be able to
    justify the validity of the results in the context of the residue.
    """
    def __init__(self):
        self.results = None
        self.residue = None

    def count(self, ballots):
        """
        The basic entry point to actual vote counting.  Takes a bunch
        of ballots (iterable), which are limited to one question
        apiece, and filtered of all spoiled responses to the question.
        Since you don't know if you are just one polling place or
        the final aggregator of all polling places, ALL BALLOTS MUST
        BE COUNTED.  (Just because your precinct heavily favors X
        doesn't mean that X will win the election!)
        """
        raise CountException('counting algorithm not provided')

    def interpret_result(self):
        """
        Returns a string which can be used to explain the results
        to a human.  The string should end with a newline.
        """
        raise CountException('results interpretation not provided')

    def interpret_residue(self):
        """
        Returns a string which can be used to explain the residue
        to a human.  The string should end with a newline.
        """
        raise CountException('residue interpretation not provided')

    def leaders(self):
        """
        Returns a list of choices which are considered to be leading, based
        on the results.
        """
        raise CountException('leaders implementation not provided')

    def trailers(self):
        """
        Returns a list of choices which are considered to be in last place,
        based on the results.
        """
        raise CountException('trailers implementation not provided')

    def are_we_there_yet(self):
        """
        Raises an exception if there are no results available.
        Returns without raising an exception otherwise.
        """
        raise CountException('going-there implementation not provided')

class FirstPastThePost(Abstract):
    """
    Your basic horse race.  The associated response format is most
    likely ChooseNoMoreThan(n) or ChooseExactly(n).  

    This is never a multi-round affair; if the results are not
    conclusive, then another election will be held with a reduced set
    of choices.  Protocols for reducing the set of choices are beyond
    the scope of this counting method.

    Results are stored as a dict with the key being the choice and the
    value being the number of votes that choice received.

    The residue is simply the number of votes counted.
    """
    def __init__(self):
        self.results = dict()
        self.residue = 0
    
    def count(self, responses):
        for response in responses:
            self.residue += 1
            for choice in response:
                try:
                    self.results[choice] += 1
                except KeyError:
                    self.results[choice] = 1

    def are_we_there_yet(self):
        if not len(self.results.keys()):
            raise IncompleteCount('nobody past the post yet')

    def interpret_results(self):
        self.are_we_there_yet()
        interpretation = ''
        for choice in self.results.keys():
            votes = self.results[choice]
            percentage = 100 * votes / self.residue
            interpretation += '%s got %d of %d votes (%.2f%%)\n' % (choice, votes, self.residue, percentage)
        return interpretation

    def interpret_residue(self):
        self.are_we_there_yet()
        return '%d total votes cast\n' % (self.residue)

    def leaders(self):
        self.are_we_there_yet()
        leader = []
        most = -1
        for choice in self.results.keys():
            if self.results[choice] == most:
                leader.append(choice)
            if self.results[choice] > most:
                most = self.results[choice]
                leader = [choice]
        return leader

    def trailers(self):
        self.are_we_there_yet()
        trailer = []
        least = self.residue
        for choice in self.results.keys():
            if self.results[choice] == least:
                trailer.append(choice)
            if self.results[choice] < least:
                least = self.results[choice]
                trailer = [choice]

        return trailer

class InstantRunoffVoting(Abstract):
    """
    http://en.wikipedia.org/wiki/Instant-runoff_voting 

    The algorithm (and its perils) are best described above, however
    here is a short summary for the lazy.  If on a given round no
    choice has more than half the votes, the choice that received the
    fewest votes is eliminated, and the ballots that listed the
    eliminated choice as their highest preference are recounted in the
    next round as if that eliminated choice were not available.

    In this implementation, if there is a last-place tie at the end of
    a round, all of those choices are disqualified for the next round.
    """

    def __init__(self):
        """
        The tally of each round depends on a FirstPastThePost
        computation.  The results attribute is in fact an instance of
        FirstPastThePost.  The residue is a list of FirstPastThePost
        instances, with the last instance being identical to the
        results.
        """
        self.residue = []
        self.results = None

    def disqualify(self, response, losers):
        """
        Returns a modified ballot, with eliminated choices removed.
        """
        return [choice for choice in response if choice not in losers]

    def count(self, responses):
        """
        A vote is considered exhausted if all of its choices are
        disqualified.
        """
        non_exhausted_votes = [x for x in responses if len(x)]
        half = int(len(non_exhausted_votes) / 2)
        first_choices = [[x[0]] for x in responses if len(x)]
        counter = FirstPastThePost()
        counter.count(first_choices)
        this_round = counter.results
        maybe_winner = counter.leaders()[0]
        self.residue.append(this_round)
        if counter.results[maybe_winner] > half:
            self.results = this_round
            return
        losers = counter.trailers()
        next_round = [self.disqualify(x, losers) for x in responses]
        self.count(next_round)

    def are_we_there_yet(self):
        if self.results is None:
            raise IncompleteCount('instant runoff still takes finite time')

    def interpret_result(self):
        self.are_we_there_yet()
        return 'Final round:\n' + self.results.interpret_results()
        
    def interpret_residue(self):
        self.are_we_there_yet()
        interpretation = ''
        ctr = 1
        for round in self.residue:
            interpretation += 'Round %d:\n' % (ctr)
            interpretation += round.interpret_results()
        return interpretation

    def leaders(self):
        self.are_we_there_yet()
        return self.results.leaders()

    def trailers(self):
        self.are_we_there_yet()
        return self.results.trailers()