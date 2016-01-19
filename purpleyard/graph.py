#!/usr/bin/env python

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import configparser
import optparse

import matplotlib
# Don't load gtk backend
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import networkx as nx

from purpleyard import gitlogs


def generate_graph(gitgraph, save, name):
    """Generate a graph of reviews.

    Args:
        gitgraph (): ProcessedGitGraph
        save (bool): True to safe graph as a png file
        name (bool): repo name
    """
    g = nx.DiGraph()
    for edge in gitgraph.weighted_graph:
        g.add_edge(edge[0], edge[1], weight=gitgraph.weighted_graph[edge])

    # node positions
    pos = nx.spring_layout(g)

    # draw nodes. Core: red, other:green
    node_color_map = ['r' if node.is_core() else 'b' for node in g.nodes()]
    nx.draw_networkx_nodes(g, pos, node_color=node_color_map,
                           node_size=700, node_shape='s')

    # draw edges
    alpha_map = [d['weight'] for (u, v, d) in g.edges(data=True)]
    max_weight = max(alpha_map)
    alpha_map = map(lambda x: x / max_weight, alpha_map)
    i = 0
    for edge in g.edges(data=True):
        nx.draw_networkx_edges(g, pos, edgelist=[edge], arrows=True, width=3,
                               alpha=alpha_map[i])
        i += 1

    # draw labels
    nx.draw_networkx_labels(g, pos, font_size=10, font_family='sans-serif')
    # from networkx.readwrite import gexf
    # gexf.write_gexf(g,'foo.gexf')
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
    optparser.add_option('-t', '--no-graph',
                         action='store_true',
                         help="Just print records, don't generate the graph")
    options, args = optparser.parse_args()

    config = configparser.ConfigParser()
    config.read('purple.ini')

    repo_path = config.get("config", "git_path") + options.repository

    gitgraph = gitlogs.ProcessedGitGraph(git_repo=repo_path, pseudonyms=options.pseudonyms)

    gitgraph.print_records()

    if not options.no_graph:
        generate_graph(gitgraph,
                       options.save,
                       options.repository.replace("/", "_"))

if __name__ == '__main__':
    main()
