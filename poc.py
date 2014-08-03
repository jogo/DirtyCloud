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

import matplotlib.pyplot as plt
import networkx as nx

# Proof of Concept

g = nx.DiGraph()


class Node(object):
    def __init__(self, name, core=True):
        super(Node, self).__init__()
        self.name = name
        self.core = core

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash(self.name)

n = [Node('0000'),
     Node('111111'),
     Node('22222', core=False),
     Node('33333'),
     Node('44444')]
g.add_nodes_from(n)

g.add_edge(n[1], n[2], weight=0.1)
g.add_edge(n[1], n[3], weight=0.9)
g.add_edge(n[1], n[4], weight=0.7)
g.add_edge(n[4], n[1], weight=0.5)


# node positions
pos = nx.spring_layout(g)

# draw nodes. Core: red, other:green
node_color_map = ['r' if node.core else 'g' for node in g.nodes()]
nx.draw_networkx_nodes(g, pos, node_color=node_color_map, node_size=700)

# draw edges
edge_weights = [d['weight'] * 10 for (u, v, d) in g.edges(data=True)]
nx.draw_networkx_edges(g, pos, arrows=True, width=edge_weights,
                       edge_color=edge_weights, edge_cmap=plt.cm.Blues)


# get top weighted edges
top_edges = sorted(g.edges_iter(data=True), key=lambda x: x[2]['weight'],
                   reverse=True)
for edge in top_edges[:-2]:
    print edge

# draw labels
nx.draw_networkx_labels(g, pos, font_size=20, font_family='sans-serif')

plt.axis('off')
plt.savefig("graph.png")
plt.show()
