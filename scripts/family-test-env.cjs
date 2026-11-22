// Replays and viewport checks reset their household. Always give them isolated fixtures.
module.exports = {
  ...process.env,
  LIVINGMIND_FAMILY_STATE_DB: '',
  LIVINGMIND_FAMILY_MIOT_PROFILE: '',
  LIVINGMIND_FAMILY_EDITOR: 'rule'
};
