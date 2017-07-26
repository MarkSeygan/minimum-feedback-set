#!/usr/bin/python
# author: Marek Zidek, Mark mff 2.rocnik

import sys, getopt
import re
import os
# potreba nainstalovat: sudo pip install networkx
import networkx as nx
import subprocess
import cStringIO
import random

# vyber prvni feasible solution / feasible solution pro skoro hotovy graf
def greedy_DAG(g, randomize=False):
    sccs = list(nx.strongly_connected_components(g))
    sccs = [g.subgraph(sc).to_directed() for sc in sccs if len(sc) > 1]  # len > 1 tedy netrivialni

    # greedy for first feasible
    cost = 0
    deleted = []

    for scc in sccs:
        while not nx.is_directed_acyclic_graph(scc):
            nodeScores = []
            if randomize:
                for node in scc.nodes():
                    if scc.in_degree(node) == 0 or scc.out_degree(node) == 0:
                        scc.node[node]['score'] = -1
                    else:
                        scc.node[node]['score'] = random.randint(1, 10)
            else:

                for node in scc.nodes():
                    if scc.in_degree(node) == 0 or scc.out_degree(node) == 0:
                        scc.node[node]['score'] = -1
                    else:
                        scc.node[node]['score'] = (abs(scc.in_degree(node) - scc.out_degree(node)))
            maxScore = 0
            maxIndex = 0
            for node in scc.nodes():
                if maxScore < scc.node[node]['score']:
                    maxScore = scc.node[node]['score']
                    maxIndex = node
            try:
                if scc[maxIndex] is None:  # case of one big cycle
                    pass
            except KeyError:
                for node in scc.nodes():
                    if scc.node[node]['score'] >= 0:
                        maxIndex = node
            if (scc.in_degree(maxIndex) == 0 or scc.out_degree(maxIndex) == 0):
                for node in scc.nodes():
                    if scc.node[node]['score'] >= 0:
                        maxIndex = node

            if scc.in_degree(maxIndex) < scc.out_degree(maxIndex):
                minWeight = min(data['weight'] for _, _, data in scc.in_edges(maxIndex, data=True))
                for u, v, data in scc.in_edges(maxIndex, data=True):
                    if data['weight'] == minWeight:
                        scc.remove_edge(u, v)
                        cost += minWeight
                        deleted.append([u, v])
                        break
            else:
                minWeight = min(data['weight'] for _, _, data in scc.out_edges(maxIndex, data=True))
                for u, v, data in scc.out_edges(maxIndex, data=True):
                    if data['weight'] == minWeight:
                        scc.remove_edge(u, v)
                        cost += minWeight
                        deleted.append([u, v])
                        break
    return cost, deleted


def main(argv):
    inputfile = ''
    outputfile = ''
    try:
        opts, args = getopt.getopt(argv, "hi:o:", ["ifile=", "ofile="])
    except getopt.GetoptError:
        print 'test.py -i <inputfile> -o <outputfile>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'test.py -i <inputfile> -o <outputfile>'
            sys.exit()
        elif opt in ("-i", "--ifile"):
            inputfile = arg
        elif opt in ("-o", "--ofile"):
            outputfile = arg
    print 'Input file is "', inputfile
    print 'Output file is "', outputfile

    input = open(os.path.join(os.path.dirname(__file__), inputfile))
    finalOutput = open(os.path.join(os.path.dirname(__file__), outputfile), 'w')

    try:
        firstline = input.readline()
        num_of_vertices = [int(s) for s in re.findall(r'\d+', firstline)][0]
        num_of_edges = [int(s) for s in re.findall(r'\d+', firstline)][1]
    except AttributeError:
        print "Nekorektni vstup"


    G = nx.DiGraph()

    z_low = 0
    for i in range(0, num_of_vertices):
        G.add_node(i)
    for i in range(0, num_of_edges):
        edge = [int(s) for s in re.findall(r'\d+', input.readline())]
        G.add_edge(edge[0], edge[1], weight=edge[2])

    originalG = G.copy()
    cost, deleted = greedy_DAG(G)
    z_high = cost

    cycle_matrix = set()

    for u, v in deleted:
        path = nx.shortest_path(originalG, source=v, target=u)
        path.append(v)
        if (path is not None):
            cycle_matrix.add(tuple(path))

    prevLP = 0
    edges_left = [1]
    randomize = False
    heuristic_count = 0
    while edges_left != []:
        # put LP into file
        put_LP_in_file(originalG, cycle_matrix, num_of_edges, randomize)
        cmd = "glpsol -m " + re.sub(" ", "\ ", str(os.path.join(os.path.dirname(__file__), "workingLP.txt")))

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        output = process.communicate()[0]

        buf = cStringIO.StringIO(output)
        c = buf.readline()
        while c[0] != '#':
            c = buf.readline()
        LPobj = [int(s) for s in re.findall(r'\d+', c)][0]
        LPdeleted = []
        c = buf.readline()
        while c[0] != '#':
            LPdeleted.append([[int(s) for s in re.findall(r'\d+', c)][0], [int(s) for s in re.findall(r'\d+', c)][1]])
            c = buf.readline()

        z_low = max(z_low, LPobj)

        if(prevLP == LPobj):
            randomize = True
            heuristic_count += 1
            if(heuristic_count == 10):
                randomize = False
                heuristic_count = 0
        else:
            randomize = False
        prevLP = LPobj
        print LPobj


        if z_low == z_high:
            # optimal
            print "done"
            finalOutput.write(output)
            break

        eliminated_graph = originalG.copy().to_directed()
        for e in LPdeleted:
            eliminated_graph.remove_edge(e[0], e[1])


        if nx.is_directed_acyclic_graph(eliminated_graph):
            # optimal
            print "done "
            finalOutput.write(output)
            break

        _, edges_left = greedy_DAG(eliminated_graph, randomize)

        new_feasible = LPdeleted + edges_left
        new_cost = sum(originalG[u][v]['weight'] for u, v in new_feasible)

        if new_cost < z_high:
            z_high = new_cost


        # pridat cykly do cycle matrix
        for u, v in edges_left:
            if randomize:
                try:
                    path = nx.shortest_path(eliminated_graph, source=v, target=u)
                    edge = random.randint(1, len(path) - 2)
                    eliminated_graph.remove_edge(path[edge], path[edge + 1])
                except nx.exception.NetworkXNoPath:
                    path = None
            try:
                path = nx.shortest_path(eliminated_graph, source=v, target=u)
            except nx.exception.NetworkXNoPath:
                path = None
            if (path is not None):
                path.append(v)

                m = min(enumerate(path), key=lambda t: t[1])[0]  # index of min element
                path = path[m:] + path[:m]  # do the actual rotation

                deleted = False
                for i in range(0, len(path) - 1):
                    if path[i] == path[i+1]:
                        del path[i]
                        deleted = True
                        break
                if deleted:
                    path.append(path[0])

                    cycle_matrix.add(tuple(path))

        '''''
        for u, v in edges_left:
            if randomize:
                try:

                path = nx.shortest_path(eliminated_graph, source=v, target=u)
                edge = random.randint(1, len(path) - 1)
                eliminated_graph.remove_edge(path[edge], path[edge+1])
                path = nx.shortest_path(eliminated_graph, source=v, target=u)
            except nx.exception.NetworkXNoPath:
                path = None
            if (path is not None):
                path.append(v)
                cycle_matrix.add(tuple(path))
        '''''





def put_LP_in_file(originalG, cycle_matrix, num_of_edges, randomize=False):
    id_of_constraight = 0

    lp = open(os.path.join(os.path.dirname(__file__), 'workingLP.txt'), 'w')

    for j in range(0, num_of_edges):
        lp.write('var y_' + str(j) + ' >=0;\n')

    hokuspokus = []

    i = 0
    for hokus in originalG.edges():
        pokus = list(hokus)
        pokus.append(i)
        hokuspokus.append(tuple(pokus))
        i += 1

    lp.write('set Edges := {' + str(hokuspokus)[1:-1] + '};\n')  # zbavit se [] zavorek

    lp.write('minimize obj: ')

    j = 0
    for _, _, data in originalG.edges(data=True):
        lp.write('y_' + str(j) + '*' + str(data['weight']) + ' + ')
        j += 1
    lp.write('0;\n')

    for cycle in cycle_matrix:
        lp.write('p' + str(id_of_constraight) + ': ')
        last = False
        for i in range(0, len(cycle)):
            if (i + 1 == len(cycle) - 1):
                indexOfEdge = originalG.edges().index((cycle[i], cycle[i + 1]))
                last = True
            else:
                indexOfEdge = originalG.edges().index((cycle[i], cycle[i + 1]))
            if last == True:
                lp.write('y_' + str(indexOfEdge) + ' >= 1;\n')
                break
            else:
                lp.write('y_' + str(indexOfEdge) + ' + ')
        id_of_constraight += 1

    lp.write('solve;\n')


    lp.write("printf \"#OUTPUT: %s \\n\", obj;\n")
    if randomize:
        treshold = random.uniform(0.5, 1.0)
    else:
        treshold = 0.55
    for i in range(0, num_of_edges):
        # lp.write("printf{(u,v,i) in Edges} \"%s\", (if(y_" + str(i) + " >= 1/2 and i == " + str(i) + ") then \"%d --> %d\" else \"\"),;\n")
        lp.write("printf {(u,v,i) in Edges: i == " + str(i) + " and y_" + str(i) + " >= " + str(treshold) + "} \"%d --> %d\\n\", u, v;\n")

    lp.write("printf \"#OUTPUT END.\\n\";\n")
    lp.write("end;")
    lp.close()


if __name__ == "__main__":
    main(sys.argv[1:])
