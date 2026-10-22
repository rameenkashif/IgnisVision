import type { components } from './schema';

type S = components['schemas'];
export type IncidentDetail = S['IncidentDetail'];
export type IncidentSummary = S['IncidentSummary'];
export type ZoneOut = S['ZoneOut'];
export type ZoneStatus = ZoneOut['status'];
export type AssignmentOut = S['AssignmentOut'];
export type MyAssignment = S['MyAssignment'];
export type AlertOut = S['AlertOut'];
export type Kpis = S['Kpis'];
export type ResponderOut = S['ResponderOut'];
export type AssessmentOut = S['AssessmentOut'];
export type IncidentCreate = S['IncidentCreate'];
