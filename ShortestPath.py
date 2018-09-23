"""

ShortestPath.py main file for ShortestPath class
"""

import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from pygeodesy import ellipsoidalVincenty as ev
import logging

class PathRenderer:

    def __init__(self,rendered_path:tuple):
        self.rendered_path = rendered_path

    def show_path_str(self):
        """
        Sort output paths for the shortest path

        :param rendered_path:
        :return:
        """

        output = ""
        for i, path in enumerate(self.rendered_path[0]):
            if i == 0:
                # print("From {} go {} to {}".format(path["start"], path["goto"], path["end"]))
                output += "Starting on {} go {} to {}\n".format(path["start"], path["goto"], path["end"])
            elif i == (self.rendered_path[2] - 1):
                # print("The destination is {} from the {}".format(path["goto"], rendered_path[0][i - 1]["start"]))
                output += "The {} is {} from the {}\n".format(self.rendered_path[0][i - 1]["end"], path["goto"],
                                                              self.rendered_path[0][i - 1]["start"])
            else:
                # print("From {} go {} about {:.2f} m to {}".format(path["start"], path["goto"], path["dist"], path["end"]))
                output += "At {}, turn {} about {:.2f} m to {}".format(path["start"], path["goto"], path["dist"], path["end"])
                if len(path["pass_by"]) > 0:
                    output += " (passing by: {})".format(",".join(path["pass_by"]))
                output += "\n"
        output += "Approximate Total Path: {:.2f} m\n".format(self.rendered_path[1])
        return output

    def show_path_map(self):
        """
        This function will show the path in the map using mpleaflet
        :return:
        """
        import mplleaflet
        plt.figure(figsize=(10, 10))
        longitude = []
        latitude = []
        for i, path in enumerate(self.rendered_path[0]):
            longitude.append(float(path["start_long"]))
            latitude.append(float(path["start_lat"]))
        longitude.append(float(path["end_long"]))
        latitude.append(float(path["end_lat"]))
        lines = plt.plot(longitude, latitude, 'b')  # Draw blue line
        # for line in lines:
        #    self.add_arrow(line)
        # latitude = np.array(latitude)
        # longitude = np.array(longitude)
        # plt.quiver(longitude,latitude)
        # plt.quiver(longitude[:-1], latitude[:-1], longitude[1:] - longitude[:-1], latitude[1:] - latitude[:-1], scale_units='xy', angles='xy', scale=1)
        plt.plot(longitude, latitude, 'rs')  # Draw red squares
        mplleaflet.show()

class ShortestPath:
    # define local properties and its file type

    # buildings, streets and edges are dataframe which are built from the csv files / dataset
    buildings: pd.DataFrame
    streets: pd.DataFrame
    edges: pd.DataFrame

    # one_direction dataframe is needed to store the street intersection
    # or street fragment that just have one direction only
    # the direction is defined from node_a to node_b on the dataframe
    one_direction: pd.DataFrame

    # inactive road, if the road in the maintanance mode, this inactive list
    # will determine which road need to be closed, direction matter, node_a is starting node_b is target
    inactive_road = pd.DataFrame

    # path_graph is a network graph for our shortest path calculation purpose
    # it contains location or intersection coordinate as a node
    # and weight / distance between two connected nodes
    # defined from the network csv datasets
    path_graph: nx.DiGraph

    def __init__(self, buildings_file: str, streets_file: str, edges_file: str):
        # read network dataset (csv files)
        self.read_network_dataset(buildings_file, streets_file, edges_file)
        # init the my_graph object using Directed graph
        self.path_graph = nx.DiGraph()
        self.buildings_to_graph()
        self.edges_to_graph()
        self.connect_building_and_street()
        self.connect_street_intersections()

    @staticmethod
    def load_file(file_name: str):
        """
        given the csv file_name this function will read the file and return a
        panda dataframe object

        :param file_name: csv file_name
        :return:
        """
        return pd.read_csv(file_name)

    def read_network_dataset(self, buildings_file: str, streets_file: str, edges_file: str,
                             one_direction: str = "one_direction.csv",inactive_road: str="inactive_road.csv"):
        """
        given the three network csv files, read all the files and assign them into
        respective properties

        :param buildings_file: buildings file name
        :param streets_file: streets file name
        :param edges_file: edges file name
        :return:
        """
        try:
            self.buildings = self.load_file(buildings_file)
            self.streets = self.load_file(streets_file)
            self.edges = self.load_file(edges_file)
            # fill not available values with empty string for the edges
            self.edges = self.edges.fillna("")
        except:
            logging.error("error loading core file, please make sure {},{}, and {} exist".format(buildings_file,streets_file,edges_file))
            exit()
        try:
            self.one_direction = self.load_file(one_direction)
        except:
            logging.error("No one direction file: {} found, there will be no one direction street defined".format(one_direction))
            self.one_direction = pd.DataFrame()
        try:
            self.inactive_road = self.load_file(inactive_road)
        except:
            logging.error("No inactive road file: {} found, there will be no inactive road defined".format(inactive_road))
            self.inactive_road = pd.DataFrame()

    def buildings_to_graph(self):
        """
        this method will insert the building dataset to the path_graph network stored as a node
        the type of the node will be building and coordinate stored in the coor atribute
        :return: None
        """
        for x in range(self.buildings.shape[0]):
            building = self.buildings.iloc[x]
            self.path_graph.add_node(building["name"], attr_dict={"type": "building", "coor": building.coordinate,
                                                                  "mail_code": building.mail_code})

    def edges_to_graph(self):
        """
        this method will insert the intersection between building and street or street and another street
        the path_graph network stored as a node
        the type of the node will be intersection and coordinate stored in the coor atribute
        the two connected point will be stored in the a and b attributes in the node
        :return: None
        """
        for x in range(self.edges.shape[0]):
            edge = self.edges.iloc[x]
            self.path_graph.add_node(edge.node_a + "-" + edge.node_b,
                                     {"type": "intersection", "a": edge.node_a, "b": edge.node_b,
                                      "coor": edge.intersection, "N": edge.N, "S": edge.S, "E": edge.E, "W": edge.W})

    @staticmethod
    def convert_bearing_to_direction(bearing: float):
        """
        given the bearing degrees, this function will convert it to the 4 directions
        :param bearing: degrees
        :return: goto, what direction is explained by the bearing degree
        >>> ShortestPath.convert_bearing_to_direction(88.23)
        'East'
        >>> ShortestPath.convert_bearing_to_direction(46)
        'East'
        >>> ShortestPath.convert_bearing_to_direction(18.23)
        'North'
        >>> ShortestPath.convert_bearing_to_direction(226)
        'West'
        >>> ShortestPath.convert_bearing_to_direction(136)
        'South'
        >>> ShortestPath.convert_bearing_to_direction(156.37)
        'South'
        >>> ShortestPath.convert_bearing_to_direction(312.3)
        'West'
        >>> ShortestPath.convert_bearing_to_direction(316)
        'North'
        """
        if bearing >= 45 and bearing < 135:
            goto = "East"
        elif bearing >= 135 and bearing < 225:
            goto = "South"
        elif bearing >= 225 and bearing < 315:
            goto = "West"
        else:
            goto = "North"
        return goto

    def connect_building_and_street(self):
        """
        this function will connect building and each street connected to the building
        this will add the edge between two nodes in path_graph

        :return: None
        """
        for x in range(self.edges.shape[0]):
            edge = self.edges.iloc[x]
            street = self.path_graph.node[edge.node_a + "-" + edge.node_b]
            building = ""
            if edge.node_a in self.path_graph.node:
                building = edge.node_a
            if edge.node_b in self.path_graph.node:
                building = edge.node_b

            if building != "":
                start = self.path_graph.node[building]
                if "coor" in start:
                    coor = start["coor"].split(",")
                    start_coor = ev.LatLon(coor[0], coor[1])

                if "coor" in street:
                    coor = street["coor"].split(",")
                    end_coor = ev.LatLon(coor[0], coor[1])
                    dist, bearing, _ = start_coor.distanceTo3(end_coor)
                    goto = self.convert_bearing_to_direction(bearing)
                    # directed graph
                    self.path_graph.add_edge(building, edge.node_a + "-" + edge.node_b,
                                             {"weight": dist, "bearing": bearing, "goto": goto})
                    bearing = bearing + 180
                    bearing = (bearing - 360) if bearing > 360 else bearing
                    goto = self.convert_bearing_to_direction(bearing)
                    self.path_graph.add_edge(edge.node_a + "-" + edge.node_b, building,
                                             {"weight": dist, "bearing": bearing, "goto": goto})

    def connect_street_intersections(self):
        """
        This function will connect the Street intersections
        and any intersections that share a same street
        The function will also calculate the weight between two intersections and
        make the edge between them in the path_graph

        :return: None
        """

        # add edge for street intersections
        for x in range(self.edges.shape[0]):
            edge = self.edges.iloc[x]
            direction = ['N', 'S', 'E', 'W']
            start_node = edge.node_a + '-' + edge.node_b
            coor = self.path_graph.node[start_node]["coor"].split(",")
            start_coor = ev.LatLon(coor[0], coor[1])
            for y in direction:
                neighbour_node = edge[y]
                # print(pd.isnull(neighbour_node))
                #if pd.isnull(neighbour_node) != True:
                if neighbour_node != "":
                    # print(neighbour_node)
                    coor = self.path_graph.node[neighbour_node]["coor"].split(",")
                    neighbour_coor = ev.LatLon(coor[0], coor[1])
                    dist, bearing, _ = start_coor.distanceTo3(neighbour_coor)
                    goto = self.convert_bearing_to_direction(bearing)
                    self.path_graph.add_edge(start_node, neighbour_node,
                                             {"weight": dist, "bearing": bearing, "goto": goto})
                    bearing = bearing + 180
                    bearing = (bearing - 360) if bearing > 360 else bearing
                    goto = self.convert_bearing_to_direction(bearing)
                    self.path_graph.add_edge(neighbour_node, start_node,
                                             {"weight": dist, "bearing": bearing, "goto": goto})

        # delete contra direction edges that are appear in the one direction file
        for x in range(self.one_direction.shape[0]):
            node_a = self.one_direction.iloc[x].node_a
            node_b = self.one_direction.iloc[x].node_b
            # remove the edge for the contra direction
            self.path_graph.remove_edge(node_b, node_a)
            # remove all edges in between

            """
            import copy
            all_edges = copy.copy(self.path_graph.edge[node_b])
            for y in all_edges:
                if node_a in self.path_graph.edge[y]:
                    self.path_graph.remove_edge(node_b, y)
                    self.path_graph.remove_edge(y, node_a)
                    # print(node_b)
                    # print(self.path_graph.edge[node_b])
            """
            for y in self.path_graph.edge[node_a]:
                # remove node that went to wrong direction in
                # between node_a and node_b
                if y in self.path_graph.edge[node_b]:
                    self.path_graph.remove_edge(node_b, y)
                    self.path_graph.remove_edge(y,node_a)
                    # print(node_b)
                    # print(self.path_graph.edge[node_b])

        # set the edges that are appear in the inactive_road file
        # with big number 9e9
        # ( can also be deleted permanently if we really don't want anything to go within that direction)
        for x in range(self.inactive_road.shape[0]):
            node_a = self.inactive_road.iloc[x].node_a
            node_b = self.inactive_road.iloc[x].node_b
            #self.path_graph.remove_edge(node_a, node_b)
            self.path_graph.edge[node_a][node_b]["weight"] = 9e9

            for y in self.path_graph.edge[node_b]:
                # remove node that are in between these node_a and node_b
                if y in self.path_graph.edge[node_a]:
                    #self.path_graph.remove_edge(node_a, y)
                    #self.path_graph.remove_edge(y, node_b)
                    self.path_graph.edge[node_a][y]["weight"] = 9e9
                    self.path_graph.edge[y][node_b]["weight"] = 9e9

        # add edge between buildings connection in the same street
        for x in range(self.streets.shape[0]):
            street = self.streets.iloc[x]
            street_name = street["name"]
            node_collection = []
            # select intersection node that have particular street name and buildings and the type
            for my_node_key in self.path_graph.node:
                my_node = self.path_graph.node[my_node_key]
                #        print(my_node)
                if my_node["type"] == "intersection":
                    if my_node["a"] == street_name or my_node["b"] == street_name:
                        building = False
                        if my_node["a"] in self.path_graph.node:
                            if self.path_graph.node[my_node["a"]]["type"] == "building":
                                building = True
                        if my_node["b"] in self.path_graph.node:
                            if self.path_graph.node[my_node["b"]]["type"] == "building":
                                building = True
                        if building:
                            node_collection.append(my_node_key)

            #print(node_collection)
            # compute distance between all buildings node in node_collection
            for node_a in node_collection:
                coor = self.path_graph.node[node_a]["coor"].split(",")
                start_coor = ev.LatLon(coor[0], coor[1])
                for node_b in node_collection:
                    # print("{} : {}".format(node_a,node_b))
                    if node_a != node_b:
                        # they should be in the same road segment (intersection)3
                        edge_a = self.path_graph.node[node_a]
                        edge_b = self.path_graph.node[node_b]
                        if edge_a["N"] == edge_b["N"] and edge_a["S"] == edge_b["S"] and edge_a["E"] == edge_b["E"] and \
                                        edge_a["W"] == edge_b["W"]:
                            coor = self.path_graph.node[node_b]["coor"].split(",")
                            end_coor = ev.LatLon(coor[0], coor[1])
                            dist, bearing, _ = start_coor.distanceTo3(end_coor)
                            goto = self.convert_bearing_to_direction(bearing)
                            # check the direction is the streat is actualy one direction or

                            directions = []
                            for edge_dir in self.path_graph.edge[node_a].values():
                                directions.append(edge_dir["goto"])
                            #print(directions)
                            
                            # add directions if it available in the connected road only
                            if goto in directions:
                                self.path_graph.add_edge(node_a, node_b, {"weight": dist, "bearing": bearing, "goto": goto})


    def render_path(self, path_node: list):
        """
        Given the path node in list format return the rendered path dictionary

        :param path_node:
        :return:
        >>> uiuc=ShortestPath(buildings_file="buildings.csv", edges_file="edges.csv", streets_file="streets.csv")
        >>> uiuc.render_path([nx.shortest_path(uiuc.path_graph,'Swanlund Administration Building', 'Ice Arena', weight="weight")]) # doctest: +ELLIPSIS
        [([{'start': 'Swanlund Administration Building',...]
        >>> uiuc.render_path([nx.shortest_path(uiuc.path_graph,'Irwin Academic Services Ctr', 'Lincoln Hall', weight="weight")]) # doctest: +ELLIPSIS
        [([{'start': 'Irwin Academic Services Ctr',...]
        >>> uiuc.render_path([nx.shortest_path(uiuc.path_graph,'abc', 'bcd', weight="weight")])
        Traceback (most recent call last):
        ...
        KeyError: 'abc'
        """
        all_path = []
        for my_node in path_node:
            temp_path = []
            total_distance = 0
            #shortest = path_node
            shortest = my_node
            j = 0
            for i, path in enumerate(shortest):
                # print(my_g.node[path])
                if i == 0:
                    start = path
                    start_node = self.path_graph.node[start]
                    latlong = start_node["coor"].split(",")
                    start_lat = latlong[0]
                    start_long = latlong[1]
                if i + 1 < len(shortest):
                    same_direction = False
                    if i == len(shortest) - 1:
                        end = shortest[i + 1]
                    else:
                        my_edge = self.path_graph.edge[path][shortest[i + 1]]
                        # print(shortest[i + 1])
                        dest_node = self.path_graph.node[shortest[i + 1]]
                        pass_by = []
                        if dest_node["type"] == "intersection":
                            if (dest_node["a"] == start):
                                end = dest_node["b"]
                            elif (dest_node["b"] == start):
                                end = dest_node["a"]
                            else:
                                # print(path)
                                # print(my_edge)
                                if last_attempt["goto"] == my_edge["goto"]:
                                    same_direction = True
                                    if last_attempt["start"] == dest_node["a"]:
                                        end = dest_node["b"]
                                    else:
                                        end = dest_node["a"]
                                else:
                                    end = "{} and {}".format(dest_node["a"], dest_node["b"])
                        else:
                            end = shortest[i + 1]
                        #print(path)
                        #print(self.path_graph.edge[path])
                        end_node = dest_node
                        latlong = end_node["coor"].split(",")
                        end_lat = latlong[0]
                        end_long = latlong[1]

                    if not same_direction:
                        last_attempt = {'start': start, 'end': end, 'dist': my_edge["weight"],
                                        'bearing': my_edge["bearing"],
                                        'goto': my_edge["goto"], "start_lat": start_lat, "start_long": start_long,
                                        "end_lat": end_lat, "end_long": end_long, "pass_by": []}
                        temp_path.append(last_attempt)
                        j += 1
                    else:
                        temp_path[j - 1]["end_lat"] = end_lat
                        temp_path[j - 1]["end_long"] = end_long
                        temp_path[j - 1]["pass_by"].append(temp_path[j - 1]["end"])
                        temp_path[j - 1]["end"] = end
                        temp_path[j - 1]["dist"] += my_edge["weight"]

                    total_distance += my_edge["weight"]
                    start = end
                    # start_node = end_node
                    start_lat = end_lat
                    start_long = end_long

            shortest_path = (temp_path, total_distance, len(temp_path))
            all_path.append(shortest_path)
        return all_path

    def shortest_path(self, where_from: str, where_to: str):
        """
        given two destinations, we use the network graph to compute the shortest path
        and return the shortest node list

        :param where_from:
        :param where_to:
        :return:
        >>> uiuc=ShortestPath(buildings_file="buildings.csv", edges_file="edges.csv", streets_file="streets.csv")
        >>> uiuc.shortest_path('Swanlund Administration Building','University YMCA')# doctest: +ELLIPSIS
        [([{'start': 'Swanlund Administration Building', ...
        >>> uiuc.shortest_path('Library and Information Sciences','Police Training Institute')# doctest: +ELLIPSIS
        [([{'start': 'Library and Information Sciences', ...
        """

        return self.render_path([nx.shortest_path(self.path_graph, where_from, where_to, weight="weight")])

    def all_path(self,where_from:str,where_to:str):
        """
        given two destinations, we use the network graph to compute the shortest path
        and return the shortest node list

        :param where_from:
        :param where_to:
        :return:

        """
        return self.render_path(nx.all_simple_paths(self.path_graph, where_from, where_to))

    def list_mail_code(self):
        """
        list mail code from the buildings panda data frame
        :return: dict = list of tuples containing the buildings name and its mailcode
        >>> uiuc=ShortestPath(buildings_file="buildings.csv", edges_file="edges.csv", streets_file="streets.csv")
        >>> uiuc.list_mail_code()# doctest: +ELLIPSIS
        [(438, '505 East Green Street'),...]
        """
        mail_codes = []
        self.buildings = self.buildings.sort_values("name", ascending=True)
        for i in range(self.buildings.shape[0]):
            mail_codes.append((self.buildings.iloc[i].mail_code, self.buildings.iloc[i]["name"]))
        return mail_codes

    def print_mail_code(self):
        """
        this functon will print mail_codes
        based on the requirement for data input
        :return:
        >>> uiuc=ShortestPath(buildings_file="buildings.csv", edges_file="edges.csv", streets_file="streets.csv")
        >>> uiuc.print_mail_code()# doctest: +ELLIPSIS
        438: 505 East Green Street
        ...

        """
        mail_codes = self.list_mail_code()
        for mail_code in mail_codes:
            print("{}: {}".format(mail_code[0], mail_code[1]))
        if self.inactive_road.shape[0] > 0 :
            print("These roads are closed due to some circumstances: ")
            for x in range(self.inactive_road.shape[0]):
                road = self.inactive_road.iloc[x]
                print("From {} to {}".format(road.node_a,road.node_b))

    def search_node_by_mail_code(self, mail_code: str):
        """
        This function will search for the mail code and
        return the respective building node
        :return: a node if mail code found, None if it is not found
        >>> uiuc=ShortestPath(buildings_file="buildings.csv", edges_file="edges.csv", streets_file="streets.csv")
        >>> uiuc.search_node_by_mail_code(343)# doctest: +ELLIPSIS

        >>> uiuc.search_node_by_mail_code(409)# doctest: +ELLIPSIS
        'University YMCA'
        >>> uiuc.search_node_by_mail_code(383)
        'Student services Arcade Building'
        """
        try:
            # convert the mail_code to integer
            # if it is happened to be error, return None
            mail_code = int(mail_code)
        except BaseException as ex:
            logging.error(ex)
            return None

        graph_node = self.path_graph.node
        # print(graph_node)
        for node in graph_node:
            if "mail_code" in graph_node[node]:
                if graph_node[node]["mail_code"] == mail_code:
                    return node
        return None

    def show_path_graph(self):
        """
        Will return the matplotlib image for network graph

        :return:
        """
        plt.figure(figsize=(10, 10))
        return nx.draw(self.path_graph, with_labels=True)

if __name__ == '__main__':
    # print mail codes
    retry = True
    uiuc = ShortestPath(buildings_file="buildings.csv", edges_file="edges.csv", streets_file="streets.csv")
    # uiuc.show_path_graph()
    # plt.show();
    while retry:
        print("Building / Mail Code list")
        uiuc.print_mail_code()
        node_a = None
        while node_a == None:
            mail_code_a = input("Input your starting mail code: ")
            node_a = uiuc.search_node_by_mail_code((mail_code_a))
            if node_a == None:
                print("Starting Mail Code {} not found, please reenter".format(mail_code_a))
        node_b = None
        while node_b == None:
            mail_code_b = input("Input your target mail code: ")
            node_b = uiuc.search_node_by_mail_code((mail_code_b))
            if node_b == None:
                print("Target Mail Code {} not found, please reenter".format(mail_code_b))
            elif node_b == node_a:
                print("Target mail code is the same with the starting mail code, please reenter")
                node_b = None

        print("Travel from {} to {}:".format(node_a, node_b))
        try:
            #all_path = uiuc.all_path(node_a,node_b)
            #print(sorted(all_path,key=lambda x:x[1])[0:1])

            shortest = uiuc.shortest_path(node_a, node_b)
            renderer = PathRenderer(shortest[0])
            #print(uiuc.render_path_str(shortest[0]))
            print(renderer.show_path_str())
            show_map = input("Show the graph map (y/N): ")
            if show_map.lower() == "y":
                #uiuc.show_path_map(shortest[0])
                renderer.show_path_map()
        except nx.exception.NetworkXNoPath as nopath:
            print("No Path found from {} to {}".format(node_a, node_b))
            logging.error(nopath)

        retry_input = input("Do you want to retry (y/N): ")
        if retry_input.lower() == "y":
            retry = True
        else:
            retry = False

    print("Thank you for using this app, see you...")
    # shortest = uiuc.shortest_path("Henry Admin Building","University YMCA")
    # print(uiuc.render_path_str(shortest))
    # shortest = uiuc.shortest_path("Noyes Laboratory","Ischool")
    # print(uiuc.render_path_str(shortest))
