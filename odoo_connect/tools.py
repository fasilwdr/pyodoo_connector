
CREATE = 0
UPDATE = 1
DELETE = 2
UNLINK = 3
LINK = 4
CLEAR = 5
SET = 6

class Command:
    @classmethod
    def create(cls, values: dict):
        """
        Create new records in the comodel using ``values``, link the created
        records to ``self``.

        In case of a :class:`~odoo.fields.Many2many` relation, one unique
        new record is created in the comodel such that all records in `self`
        are linked to the new record.

        In case of a :class:`~odoo.fields.One2many` relation, one new record
        is created in the comodel for every record in ``self`` such that every
        record in ``self`` is linked to exactly one of the new records.

        Return the command triple :samp:`(CREATE, 0, {values})`
        """
        return (CREATE, 0, values)

    @classmethod
    def update(cls, id: int, values: dict):
        """
        Write ``values`` on the related record.

        Return the command triple :samp:`(UPDATE, {id}, {values})`
        """
        return (UPDATE, id, values)

    @classmethod
    def delete(cls, id: int):
        """
        Remove the related record from the database and remove its relation
        with ``self``.

        In case of a :class:`~odoo.fields.Many2many` relation, removing the
        record from the database may be prevented if it is still linked to
        other records.

        Return the command triple :samp:`(DELETE, {id}, 0)`
        """
        return (DELETE, id, 0)

    @classmethod
    def unlink(cls, id: int):
        """
        Remove the relation between ``self`` and the related record.

        In case of a :class:`~odoo.fields.One2many` relation, the given record
        is deleted from the database if the inverse field is set as
        ``ondelete='cascade'``. Otherwise, the value of the inverse field is
        set to False and the record is kept.

        Return the command triple :samp:`(UNLINK, {id}, 0)`
        """
        return (UNLINK, id, 0)

    @classmethod
    def link(cls, id: int):
        """
        Add a relation between ``self`` and the related record.

        Return the command triple :samp:`(LINK, {id}, 0)`
        """
        return (LINK, id, 0)

    @classmethod
    def clear(cls):
        """
        Remove all records from the relation with ``self``. It behaves like
        executing the `unlink` command on every record.

        Return the command triple :samp:`(CLEAR, 0, 0)`
        """
        return (CLEAR, 0, 0)

    @classmethod
    def set(cls, ids: list):
        """
        Replace the current relations of ``self`` by the given ones. It behaves
        like executing the ``unlink`` command on every removed relation then
        executing the ``link`` command on every new relation.

        Return the command triple :samp:`(SET, 0, {ids})`
        """
        return (SET, 0, ids)