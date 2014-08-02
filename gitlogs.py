import collections
import json
import os
import random
import subprocess


class Node(object):
    def __init__(self, name):
        super(Node, self).__init__()
        self.name = name
        self.emails = []
        self.review_count = 0
        self.patch_count = 0

    def is_core(self):
        # Since currently only using git notes this isn't precise
        return self.review_count > 3

    def __repr__(self):
        return self.name


class RawGitGraph(object):
    """Extract gerrit +2 reviews from  git logs with notes.

    Core reviewer defined as someone who can do "Code-Review+2: ".
    Generates a list of edges: (Reviewer, Author)
    """

    def __init__(self, git_repo='/home/jogo/Develop/openstack/nova'):
        # TODO move path to config file
        super(RawGitGraph, self).__init__()
        # up to date mailmap file
        # http://git.openstack.org/cgit/stackforge/stackalytics/plain/etc/default_data.json
        # TODO(jogo) download new version if internet, else look for local copy

        with open('stackalytics.json') as data:
            self.stackalytics = json.load(data)
        self.git_repo = git_repo
        self.nodes = dict()  # string:node_object
        self.commits = self.get_git_commits()
        self.unweighted_graph = self.generate_raw_git_graph()

    def get_git_commits(self):
        """Get git log with gerrit notes."""
        cwd = os.getcwd()
        os.chdir(self.git_repo)
        # gerrit ref for notes
        command = ("git log --notes=refs/notes/review "
                   "--no-merges --since=6.month")
        log = subprocess.check_output(command.split(' '))
        os.chdir(cwd)
        commits = log.split("\ncommit ")
        return commits

    def generate_raw_git_graph(self):
        """Generate list of edges based on git logs.

        list = [(Reviewer,Author),(Reviewer2, Author)]
        """
        edges = []
        for commit in self.commits:
            edge = self.parse_commit(commit)
            if len(edge) == 0:
                # something went wrong
                continue
            edges = edges + edge
        return edges

    def parse_commit(self, commit):
        """Extract author and +2 reviewers from commit."""
        edges = []
        for line in commit.split('\n'):
            if line.startswith("Author: "):
                author = self.get_node(line)
                author.patch_count += 1
                break
        for reviewer in self.get_core_reviewers_on_commit(commit):
            reviewer.review_count += 1
            edges.append((reviewer, author))
        return edges

    def get_core_reviewers_on_commit(self, commit):
        """Extract core reviewers on a specific commit."""
        reviewers = []
        notes = False
        for line in commit.split('\n'):
            if line.strip() == "Notes (review):":
                # Make sure we ignore the git commit message
                notes = True
            elif notes and "Code-Review+2: " in line:
                reviewers.append(self.get_node(line))
        return reviewers

    def get_node(self, line):
        name = self.get_name_from_git_logs(line)
        if name not in self.nodes:
            self.nodes[name] = Node(name)
        return self.nodes[name]

    def get_name_from_git_logs(self, line):
        """Parse git log to find email."""
        # https://github.com/networkx/networkx/issues/1230
        return repr(self.get_stackalytics_user_name(line.split()[-1][1:-1]))

    def get_stackalytics_user_name(self, email):
        for user in self.stackalytics["users"]:
            if email in list(user['emails']):
                for company in user['companies']:
                    if not company['end_date']:
                        return ("%s (%s)" % (user['user_name'],
                                company['company_name']))
                return user['user_name']
        return email


class ProcessedGitGraph(RawGitGraph):
    def __init__(self, git_repo):
        super(ProcessedGitGraph, self).__init__(git_repo=git_repo)
        self.weighted_graph = self.weight_graph()

    def count_edges(self):
        # key: (Reviewer,Author), value:edge count
        weighted = collections.defaultdict(float)
        # weigh edges
        for edge in self.unweighted_graph:
            weighted[edge] += 1
        return weighted

    def weight_graph(self):
        """Assign weights to edges.

        Weight of edge ReviewerA->AuthorB:
        weight = (# duplicate edges)/(# of reviews by ReviewerA)
        """
        # key: (Reviewer,Author), value:weight
        weighted = self.count_edges()
        # normalize weights by total reviews per reviewer
        for edge in weighted:
            weighted[edge] = weighted[edge]/edge[0].review_count
        # clean up data
        hit_list = set([])
        for edge in weighted:
            # sanity check, if any weights are 1, remove.
            if weighted[edge] > 0.99:
                hit_list.add(edge)
            # if reviewer has less then 3 core reviews, probably
            # not a core
            if not edge[0].is_core():
                hit_list.add(edge)
            # if author core and less then x commits
            if (not edge[1].is_core() and edge[1].patch_count < 10):
                hit_list.add(edge)
        for hit in hit_list:
            del weighted[hit]
        return weighted

    def get_strongest_edges(self, n=20):
        """"Return list with top n strongest edges with raw edge numbers."""
        # Get raw numbers
        raw = dict()
        edge_count = self.count_edges()
        for key in self.weighted_graph.keys():
            reviewer = key[0]
            raw[key] = (edge_count[key], reviewer.review_count)
        # Sort dict by key
        strongest = sorted(raw.iteritems(), key=lambda x: (x[1][0]/x[1][1]),
                           reverse=True)
        return strongest[:n]

    def print_records(self):
        print "((Reviewer, Author)): weight (hits/reviews))"
        for x in self.get_strongest_edges():
            key, (hits, reviews) = x
            print "'%s': %f (%d/%d)" % (key, hits/reviews, hits, reviews, )


class AnonimizedGitGraph(ProcessedGitGraph):
    """Replace emails with pseudonyms."""

    def __init__(self, git_repo):
        random.seed()
        self.email_map = dict()
        super(AnonimizedGitGraph, self).__init__(git_repo=git_repo)

    def get_name_from_git_logs(self, line):
        """Parse git log to find email."""
        email = super(AnonimizedGitGraph, self).get_name_from_git_logs(line)
        return self.anonimize_email(email)

    def anonimize_email(self, email):
        # anonimize
        if email not in self.email_map:
            self.email_map[email] = self.get_unique_random_name()
        return self.email_map[email]

    def get_unique_random_name(self, n=1000):
        # Generate up to n random names
        if len(self.email_map) is n:
            # no more random names left in space
            raise Exception("No more random names left")
        while True:
            rand = str(int(random.random()*n))
            if rand not in self.email_map.values():
                return rand
