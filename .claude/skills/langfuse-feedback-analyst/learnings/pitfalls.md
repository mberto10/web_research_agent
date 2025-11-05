# Common Pitfalls

## Suggesting Changes to Unused Config Fields

Config files contain many fields for documentation purposes that are never read by the generation system. Recommending changes to these unused fields produces no improvement in content quality.

**Solution:** Always verify the target field exists in `CONFIG_FIELD_USAGE_MAP.md` before recommending changes.
