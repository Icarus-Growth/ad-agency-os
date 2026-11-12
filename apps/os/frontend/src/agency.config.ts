/* What this agency is: an ads agency (done for you).
 *
 * The boards, their stage ladders, the fields on a card, the agency's own columns on the client
 * page and the weekly numbers. Change a stage here AND in the database, then run
 * `python3 tests/config_matches_db.py`. */
import type { AgencyConfig, Ladders } from './config';

/** The agency's own database lists. They must match the migrations exactly. */
export const LADDERS = {
  creative_stage: [
    '0 - To Script',
    '10 - Script Review',
    '19 - Script Changes',
    '20 - Awaiting Footage',
    '30 - To Edit',
    '39 - Redo Requested',
    '40 - Internal Review',
    '49 - Client Changes',
    '50 - Client Review',
    '60 - Ready To Launch',
    '100 - Launched',
  ],
  creative_format: ['Video'],
  ad_campaign_stage: [
    '0 - Backlog',
    '10 - Planning',
    '20 - Building',
    '30 - Client Approval',
    '40 - Ready To Launch',
    '50 - Live',
    '60 - Optimising',
    '100 - Ended',
  ],
} as const satisfies Ladders;

export const AGENCY: AgencyConfig = {
  agency: 'Ads',
  boards: [
    {
      table: 'creatives',
      label: 'Editing pipeline',
      item: 'creative',
      desc: 'One card is one ad creative for one client, from script to launched.',
      nameKey: 'creative_name',
      stageKey: 'stage',
      ladder: 'creative_stage',
      closed: ['100 - Launched'],
      clientRequired: true,
      card: ['ad_campaign_id', 'assignee_id', 'due_date'],
      sections: [
        { title: 'Basic details', desc: 'What the creative is, for which client and campaign, and who works on it.', fields: [
          { key: 'creative_name', label: 'Creative', type: 'text', required: true },
          { key: 'client_id', label: 'Client', type: 'client', required: true },
          { key: 'ad_campaign_id', label: 'Campaign', type: 'card', board: 'ad_campaigns', desc: 'The ad campaign this creative runs in. Pick a campaign of the same client.' },
          { key: 'assignee_id', label: 'Assignee', type: 'person', desc: 'Who must act now: the script writer, then the editor.' },
          { key: 'reviewer_id', label: 'Reviewer', type: 'person', desc: 'Who checks the script and the edit.' },
          { key: 'format', label: 'Format', type: 'choice', list: 'creative_format' },
        ] },
        { title: 'Script', desc: 'For the script writer: the angle, the hook and the script.', fields: [
          { key: 'due_date', label: 'Due date', type: 'date' },
          { key: 'angle', label: 'Angle', type: 'text' },
          { key: 'hook', label: 'Hook', type: 'text' },
          { key: 'script', label: 'Script', type: 'document', link: 'script_url', check: 'ad-script' },
        ] },
        { title: 'Edit', desc: 'For the editor: the raw footage and the finished cut.', fields: [
          { key: 'raw_footage_url', label: 'Raw footage', type: 'url' },
          { key: 'edited_url', label: 'Finished cut', type: 'url' },
        ] },
        { title: 'Launch', desc: 'For the media buyer: the launch date fills itself when the card reaches Launched.', fields: [
          { key: 'launch_date', label: 'Launch date', type: 'date' },
          { key: 'ad_id', label: 'Ad ID', type: 'text' },
        ] },
        { title: 'Feedback and notes', desc: 'What the reviewer or the client asked to change.', fields: [
          { key: 'feedback_notes', label: 'Feedback', type: 'longtext' },
          { key: 'notes', label: 'Notes', type: 'longtext' },
        ] },
      ],
      create: ['creative_name', 'client_id', 'ad_campaign_id', 'assignee_id', 'due_date'],
    },
    {
      table: 'ad_campaigns',
      label: 'Campaigns',
      item: 'campaign',
      desc: 'One card is one ad campaign for one client, from planning to ended. A live campaign stays open.',
      nameKey: 'campaign_name',
      stageKey: 'stage',
      ladder: 'ad_campaign_stage',
      closed: ['100 - Ended'],
      live: ['50 - Live', '60 - Optimising'],
      clientRequired: true,
      card: ['client_id', 'assignee_id', 'due_date'],
      sections: [
        { title: 'Basic details', desc: 'What the campaign is, for which client, and who works on it.', fields: [
          { key: 'campaign_name', label: 'Campaign', type: 'text', required: true },
          { key: 'client_id', label: 'Client', type: 'client', required: true },
          { key: 'assignee_id', label: 'Assignee', type: 'person', desc: 'Who must act now: the media buyer, as a rule.' },
          { key: 'due_date', label: 'Due date', type: 'date' },
        ] },
        { title: 'Campaign details', desc: 'For the media buyer: where it runs, what it is for, and the brief.', fields: [
          { key: 'platform', label: 'Platform', type: 'text', desc: 'For example Meta, Google, TikTok or LinkedIn.' },
          { key: 'objective', label: 'Objective', type: 'text', desc: 'For example leads, sales or calls booked.' },
          { key: 'brief_doc', label: 'Brief', type: 'document', link: 'brief_doc_url', desc: 'The campaign brief: the offer, the audience and the angles to test.' },
          { key: 'launch_date', label: 'Launch date', type: 'date' },
          { key: 'end_date', label: 'End date', type: 'date' },
        ] },
        { title: 'Results and notes', desc: 'What the campaign did, and what to change next.', fields: [
          { key: 'results_notes', label: 'Results', type: 'longtext' },
          { key: 'notes', label: 'Notes', type: 'longtext' },
        ] },
      ],
      create: ['campaign_name', 'client_id', 'assignee_id', 'due_date'],
    },
  ],
  lists: [],
  clientSections: [
    { title: 'People', desc: 'Who looks after this client in each role.', fields: [
      { key: 'account_manager_id', label: 'Account manager', type: 'person' },
      { key: 'media_buyer_id', label: 'Media buyer', type: 'person' },
      { key: 'editor_id', label: 'Editor', type: 'person' },
    ] },
    { title: 'Ads', desc: 'Where the ads run and what the team needs to make them.', fields: [
      { key: 'market', label: 'Market', type: 'text' },
      { key: 'ad_platform', label: 'Ad platform', type: 'text' },
      { key: 'ad_account_id', label: 'Ad account number', type: 'text', desc: 'Never a login or a token.' },
      { key: 'ad_account_access', label: 'We have ad account access', type: 'bool' },
      { key: 'monthly_ad_budget', label: 'Monthly ad budget', type: 'money' },
      { key: 'lead_sheet_url', label: 'Lead sheet', type: 'url' },
      { key: 'footage_folder_url', label: 'Footage folder', type: 'url' },
    ] },
  ],
  metrics: [
    { key: 'spend', label: 'Spend', format: 'money' },
    { key: 'leads', label: 'Leads', format: 'int' },
    { key: 'cost_per_lead', label: 'Cost per lead', format: 'money' },
    { key: 'calls_booked', label: 'Calls booked', format: 'int' },
  ],
};
