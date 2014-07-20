import matplotlib.pyplot as plt
import networkx as nx

# Proof of Concept

g = nx.MultiDiGraph()


g.add_edge('1','2',weight=0.1)
g.add_edge('1','3',weight=0.9)
g.add_edge('1','4',weight=0.9)
g.add_edge('4','1',weight=0.5)



elarge=[(u,v) for (u,v,d) in g.edges(data=True) if d['weight'] > 0.5]
esmall=[(u,v) for (u,v,d) in g.edges(data=True) if d['weight'] <= 0.5]

# node positions
pos=nx.spring_layout(g)

# draw nodes
nx.draw_networkx_nodes(g,pos,node_size=700)

# draw edges
nx.draw_networkx_edges(g,pos,edgelist=elarge,width=6,arrows=True)
nx.draw_networkx_edges(g,pos,edgelist=esmall,width=6,alpha=0.5,edge_color='b',
        style='dashed')


#draw labels
nx.draw_networkx_labels(g,pos,font_size=20,font_family='sans-serif')

plt.axis('off')
plt.savefig("graph.png")
plt.show()
