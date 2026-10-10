-- Dictionarry commit d5fa005beb, supplied by the user. Preserve the typo
-- here so the regression exercises the real upstream migration.
DELETE FROM custom_format_conditions
 WHERE custom_format_name = 'Remux Tier 3'
 AND name = 'SiCFoI' AND type = 'release_group'
 AND arr_type = 'all' AND negate = 0 AND required = 0;
INSERT INTO custom_format_conditions (custom_format_name, name, type, arr_type, negate, required)
VALUES ('Remux Tier 4', 'SiCFoI', 'release_title', 'all', 0, 0);
INSERT INTO condition_patterns (custom_format_name, condition_name, regular_expression_name)
VALUES ('Remux Tier 4', 'SiCFoI', 'SiCFoI');
