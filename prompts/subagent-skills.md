Absorb skills on-demand based on the topic.

INPUT: topic key, project slug.

TOOLS: bash, read.

RULES:
- First check if skills already absorbed: guardian absorb status <slug>
- If topic matches available skills, absorb them:
  guardian_absorb.py scan
  guardian_absorb.py match <slug>
  guardian_absorb.py ingest <slug>
- Only absorb if relevant. No bulk.
- Save result in brain:
  guardian brain write episodic skill_absorb "topic:skills" --importance 0.5

OUTPUT: SOLO 3 lineas. Nada mas. No preguntes.
STATUS: absorbed | already_have | no_match | error
SKILLS: skills absorbidos (o ninguno)
REASON: por que se absorbio (o por que no)
