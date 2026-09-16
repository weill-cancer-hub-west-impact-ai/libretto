import { get, writable, type Writable } from 'svelte/store';
import type { ExtractionSpec, Patient } from '../extraction_types.js';
import { authenticatedFetch } from './auth.js';

export const projectID: Writable<number | null> = writable(null);
export const patients: Writable<Patient[] | null> = writable(null);
export const selectedPatient: Writable<Patient | null> = writable(null);
export const specs: Writable<ExtractionSpec[] | null> = writable(null);
export const selectedSpec: Writable<ExtractionSpec | null> = writable(null);

export async function loadPatients(specID: string | null = null): Promise<Patient[] | null> {
  let proj = get(projectID);
  try {
    let result = await authenticatedFetch(
      specID !== null
        ? `/api/projects/${proj}/patients?specID=${specID}&full=0`
        : `/api/projects/${proj}/patients?full=0`
    );
    if (result.ok) {
      return await result.json();
    } else return null;
  } catch (e) {
    console.warn('Error loading patients: ' + e);
    return null;
  }
}

export async function syncPatients() {
  patients.set(await loadPatients());
}

export async function getPatientDetails(
  patientID: string,
  specID: string | undefined = undefined
): Promise<Patient | null> {
  let proj = get(projectID);
  try {
    let result = await authenticatedFetch(
      `/api/projects/${proj}/patients/${patientID}` + (!!specID ? `?specID=${specID}` : '')
    );
    if (!result.ok) return null;
    return await result.json();
  } catch (e) {
    return null;
  }
}

export async function loadSpecs(): Promise<ExtractionSpec[] | null> {
  let proj = get(projectID);
  try {
    let result = await authenticatedFetch(`/api/projects/${proj}/specs`);
    if (result.ok) {
      return await result.json();
    } else return null;
  } catch (e) {
    console.warn('Error loading specs: ' + e);
    return null;
  }
}

export async function syncSpecs() {
  specs.set(await loadSpecs());
}
