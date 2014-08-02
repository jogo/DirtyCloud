#!/usr/bin/env python

import matplotlib.pyplot as plt
import optparse

import networkx as nx

import gitlogs


def generate_graph(gitgraph, save, name):
    g = nx.DiGraph()
    for edge in gitgraph.weighted_graph:
        g.add_edge(edge[0], edge[1], weight=gitgraph.weighted_graph[edge])

    # node positions
    pos = nx.spring_layout(g, iterations=400)

    # draw nodes. Core: red, other:green
    node_color_map = ['r' if node.is_core() else 'b' for node in g.nodes()]
    nx.draw_networkx_nodes(g, pos, node_color=node_color_map,
                           node_size=700, node_shape='s')



    # draw edges
    alpha_map = [d['weight'] for (u, v, d) in g.edges(data=True)]
    max_weight = max(alpha_map)
    alpha_map = map(lambda x: x/max_weight, alpha_map)
    i = 0
    for edge in g.edges(data=True):
        nx.draw_networkx_edges(g, pos, edgelist=[edge], arrows=True, width=3,
                               alpha=alpha_map[i])
        i+=1

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

    # TODO don't hard code this
    repo_path = '/home/jogo/Develop/' + options.repository

    if options.pseudonyms:
        gitgraph = gitlogs.AnonimizedGitGraph(git_repo=repo_path)
    else:
        gitgraph = gitlogs.ProcessedGitGraph(git_repo=repo_path)

    gitgraph.print_records()

    generate_graph(gitgraph,
                   options.save,
                   options.repository.replace("/", "_"))

if __name__ == '__main__':
    main()
