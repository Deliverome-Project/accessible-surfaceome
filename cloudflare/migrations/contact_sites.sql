CREATE TABLE IF NOT EXISTS contact_release (
 release_id TEXT PRIMARY KEY, manifest_json TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('loading','validated')), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS contact_active_release (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), release_id TEXT NOT NULL REFERENCES contact_release(release_id)
);
CREATE TABLE IF NOT EXISTS contact_gene (
 release_id TEXT NOT NULL REFERENCES contact_release(release_id), uniprot_acc TEXT NOT NULL, hgnc_id TEXT NOT NULL,
 summary_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL, PRIMARY KEY(release_id,uniprot_acc)
);
CREATE TABLE IF NOT EXISTS contact_ligand (
 release_id TEXT NOT NULL REFERENCES contact_release(release_id), ligand_id TEXT NOT NULL, identity_json TEXT NOT NULL,
 PRIMARY KEY(release_id,ligand_id)
);
CREATE TABLE IF NOT EXISTS contact_gene_ligand (
 release_id TEXT NOT NULL, uniprot_acc TEXT NOT NULL, ligand_id TEXT NOT NULL, association_json TEXT NOT NULL,
 PRIMARY KEY(release_id,uniprot_acc,ligand_id),
 FOREIGN KEY(release_id,uniprot_acc) REFERENCES contact_gene(release_id,uniprot_acc),
 FOREIGN KEY(release_id,ligand_id) REFERENCES contact_ligand(release_id,ligand_id)
);
CREATE TABLE IF NOT EXISTS contact_observation (
 release_id TEXT NOT NULL, observation_id TEXT NOT NULL, uniprot_acc TEXT NOT NULL, ligand_id TEXT NOT NULL,
 source TEXT NOT NULL, context TEXT NOT NULL, observation_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 PRIMARY KEY(release_id,observation_id),
 FOREIGN KEY(release_id,uniprot_acc,ligand_id) REFERENCES contact_gene_ligand(release_id,uniprot_acc,ligand_id)
);
CREATE INDEX IF NOT EXISTS contact_observation_lookup ON contact_observation(release_id,uniprot_acc,ligand_id,observation_id);
