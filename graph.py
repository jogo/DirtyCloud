#!/usr/bin/env python

import optparse

import matplotlib.pyplot as plt
import networkx as nx

import gitlogs


def generate_graph(gitgraph, save, name):
    g = nx.MultiDiGraph()
    for edge in gitgraph.weighted_graph:
        g.add_edge(edge[0], edge[1], weight=gitgraph.weighted_graph[edge])

    # Use three different style edges to highlight larger weights
    min_weight, max_weight = gitgraph.get_weight_range()
    delta = (max_weight-min_weight)/3.0
    first = min_weight + delta
    second = first + delta
    esmall = [(u, v) for (u, v, d) in g.edges(data=True)
              if d['weight'] <= first]
    emedium = [(u, v) for (u, v, d) in g.edges(data=True)
               if d['weight'] <= second and d['weight'] > first]
    elarge = [(u, v) for (u, v, d) in g.edges(data=True)
              if d['weight'] > second]

    # node positions
    pos = nx.spring_layout(g)

    # draw nodes
    nx.draw_networkx_nodes(g, pos, node_size=700, node_shape='s')

    # draw edges
    nx.draw_networkx_edges(g, pos, edgelist=elarge, width=6, edge_color='g',
                           arrows=True)
    nx.draw_networkx_edges(g, pos, edgelist=emedium, width=6, edge_color='g',
                           arrows=True, alpha=0.6)
    nx.draw_networkx_edges(g, pos, edgelist=esmall, width=6, alpha=0.3,
                           edge_color='b', style='dashed')

    # draw labels
    nx.draw_networkx_labels(g, pos, font_size=10, font_family='sans-serif')

    plt.axis('off')
    if save:
        plt.savefig("%s.png" % name)
    plt.show()


def main():
    optparser = optparse.OptionParser()
    optparser.add_option('-r', '--repository',
                         default='openstack/nova',
                         help='specify repository to analyze')
    optparser.add_option('-p', '--pseudonyms',
                         action='store_true',
                         help='Use pseudonyms instead of email addresses')
    optparser.add_option('-s', '--save',
                         action='store_true',
                         help='Save image')
    options, args = optparser.parse_args()

    repo_path = '/home/jogo/Develop/' + options.repository

    if options.pseudonyms:
        gitgraph = gitlogs.AnonimizedGitGraph(git_repo=repo_path)
    else:
        gitgraph = gitlogs.ProcessedGitGraph(git_repo=repo_path)

    print "weights"
    print "min: %s, max: %s" % gitgraph.get_weight_range()
    print
    print "((Reviewer, Author)): weight (hits/reviews))"
    for x in gitgraph.get_strongest_edges():
        key, (hits, reviews) = x
        print "'%s': %f (%d/%d)" % (key, hits/reviews, hits, reviews, )

    generate_graph(gitgraph,
                   options.save,
                   options.repository.replace("/", "_"))

if __name__ == '__main__':
    main()
