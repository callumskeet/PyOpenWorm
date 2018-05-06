from __future__ import print_function

from wrapt import ObjectProxy
from PyOpenWorm.pProperty import Property
from PyOpenWorm.cell import Cell
from PyOpenWorm.connection import Connection


# XXX: Should we specify somewhere whether we have NetworkX or something else?

class NeuronProxy(ObjectProxy):

    def __init__(self, neighbor, connection, *args):
        super(NeuronProxy, self).__init__(*args)
        self._self_neighbor = neighbor
        self._self_connection = connection

    @property
    def neighbor(self):
        return self._self_neighbor

    @property
    def connection(self):
        return self._self_connection


class Neuron(Cell):

    """
    A neuron.

    See what neurons express some neuropeptide

    Example::

        # Grabs the representation of the neuronal network
        >>> net = P.Worm().get_neuron_network()

        # Grab a specific neuron
        >>> aval = net.aneuron('AVAL')

        >>> aval.type()
        set([u'interneuron'])

        #show how many connections go out of AVAL
        >>> aval.connection.count('pre')
        77

        >>> aval.name()
        u'AVAL'

        #list all known receptors
        >>> sorted(aval.receptors())
        [u'GGR-3', u'GLR-1', u'GLR-2', u'GLR-4', u'GLR-5', u'NMR-1', u'NMR-2', u'UNC-8']

        #show how many chemical synapses go in and out of AVAL
        >>> aval.Syn_degree()
        90

    Parameters
    ----------
    name : string
        The name of the neuron.

    Attributes
    ----------
    type : DatatypeProperty
        The neuron type (i.e., sensory, interneuron, motor)
    receptor : DatatypeProperty
        The receptor types associated with this neuron
    innexin : DatatypeProperty
        Innexin types associated with this neuron
    neurotransmitter : DatatypeProperty
        Neurotransmitters associated with this neuron
    neuropeptide : DatatypeProperty
        Name of the gene corresponding to the neuropeptide produced by this neuron
    neighbor : Property
        Get neurons connected to this neuron if called with no arguments, or
        with arguments, state that neuronName is a neighbor of this Neuron
    connection : Property
        Get a set of Connection objects describing chemical synapses or gap
        junctions between this neuron and others

    """

    class_context = Cell.class_context

    def __init__(self, name=False, **kwargs):
        super(Neuron, self).__init__(name=name, **kwargs)
        # Get neurons connected to this neuron
        Neighbor(owner=self)
        # Get connections from this neuron
        ConnectionProperty(owner=self)

        Neuron.DatatypeProperty("type", self, multiple=True)
        Neuron.DatatypeProperty("receptor", self, multiple=True)
        Neuron.DatatypeProperty("innexin", self, multiple=True)
        Neuron.DatatypeProperty("neurotransmitter", self, multiple=True)
        Neuron.DatatypeProperty("neuropeptide", self, multiple=True)
        ### Aliases ###
        self.get_neighbors = self.neighbor
        self.receptors = self.receptor

    def contextualize(self, context):
        res = super(Neuron, self).contextualize(context)
        if hasattr(self, 'neighbor'):
            res = NeuronProxy(self.neighbor.contextualize(context),
                              self.connection.contextualize(context),
                              res)
        return res

    def GJ_degree(self):
        """Get the degree of this neuron for gap junction edges only

        :returns: total number of incoming and outgoing gap junctions
        :rtype: int
        """
        count = 0
        for c in self.connection():
            if c.syntype.one() == 'gapJunction':
                count += 1
        return count

    def Syn_degree(self):
        """Get the degree of this neuron for chemical synapse edges only

        :returns: total number of incoming and outgoing chemical synapses
        :rtype: int
        """
        count = 0
        for c in self.connection.get('either'):
            if c.syntype.one() == 'send':
                count += 1
        return count

    def _type_networkX(self):
        """Get type of this neuron (motor, interneuron, sensory)

        Use the networkX representation as the source

        :returns: the type
        :rtype: str
        """
        return self['nx'].node[self.name.one()]['ntype']

    def get_incidents(self, type=0):
        """ Get neurons which synapse at this neuron """
        # Directed graph. Getting accessible _from_ this node
        for item in self['nx'].in_edges_iter(self.name(), data=True):
            if 'GapJunction' in item[2]['synapse']:
                yield item[0]

    def _as_neuroml(self):
        """Return this neuron as a NeuroML representation

           :rtype: libNeuroML.Neuron
        """


class Neighbor(Property):
    multiple = True

    def __init__(self, **kwargs):
        super(Neighbor, self).__init__('neighbor', **kwargs)
        self._conns = []
        self._conntype = Connection.contextualize(self.owner.context)

    def get(self, **kwargs):
        """Get a list of neighboring neurons.

           Parameters
           ----------
           See parameters for PyOpenWorm.connection.Connection

           Returns
           -------
           list of Neuron
        """
        if len(self._conns) > 0:
            for c in self._conns:
                for post in c.post_cell.get():
                    yield post
        else:
            c = self._conntype.contextualize(self.context)(pre_cell=self.owner, **kwargs)
            for r in c.load():
                yield r.post_cell()

    @property
    def defined_values(self):
        return []

    @property
    def values(self):
        return []

    def set(self, other, **kwargs):
        c = self._conntype(pre_cell=self.owner, post_cell=other, **kwargs)
        self._conns.append(c)
        return c

    def triples(self, **kwargs):
        for c in self._conns:
            for x in c.triples(**kwargs):
                yield x


class ConnectionProperty(Property):

    """A representation of the connection between neurons. Either a gap junction
    or a chemical synapse

    TODO: Add neurotransmitter type.
    TODO: Add connection strength
    """

    multiple = True

    def __init__(self, **kwargs):
        super(ConnectionProperty, self).__init__('connection', **kwargs)
        self._conns = []
        self._conntype = Connection

    def get(self, pre_post_or_either='pre', **kwargs):
        """Get a list of connections associated with the owning neuron.

           Parameters
           ----------
           type: What kind of junction to look for.
                        0=all, 1=gap junctions only, 2=all chemical synapses
                        3=incoming chemical synapses, 4=outgoing chemical synapses
           Returns
           -------
           list of Connection
        """
        c = []
        if pre_post_or_either == 'pre':
            c.append(self._conntype(pre_cell=self.owner, **kwargs))
        elif pre_post_or_either == 'post':
            c.append(self._conntype(post_cell=self.owner, **kwargs))
        elif pre_post_or_either == 'either':
            c.append(self._conntype(pre_cell=self.owner, **kwargs))
            c.append(self._conntype(post_cell=self.owner, **kwargs))
        for x in c:
            for r in x.load():
                yield r

    @property
    def values(self):
        return []

    def count(self, pre_post_or_either='pre', syntype=None, *args, **kwargs):
        c = []
        conntype = self._conntype.contextualize(self.context)
        if pre_post_or_either == 'pre':
            c.append(conntype(pre_cell=self.owner, **kwargs))
        elif pre_post_or_either == 'post':
            c.append(conntype(post_cell=self.owner, **kwargs))
        elif pre_post_or_either == 'either':
            c.append(conntype(pre_cell=self.owner, **kwargs))
            c.append(conntype(post_cell=self.owner, **kwargs))
        res = 0
        for x in c:
            res += sum(1 for _ in x.load())
        return res

    def set(self, conn, **kwargs):
        """Add a connection associated with the owner Neuron

           Parameters
           ----------
           conn : PyOpenWorm.connection.Connection
               connection associated with the owner neuron

           Returns
           -------
           A PyOpenWorm.neuron.Connection
        """
        assert(isinstance(conn, self._conntype))
        self._conns.append(conn)

    def triples(self, **kwargs):
        for c in self._conns:
            for x in c.triples(**kwargs):
                yield x


__yarom_mapped_classes__ = (Neuron,)
