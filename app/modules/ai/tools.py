"""Defined functions and tools for the DocMed AI Assistant.
The AI chatbot interacts strictly through these defined functions.
All queries are safe, scoped to the authenticated user's permissions.
"""

from typing import Dict, Any, List
from flask_login import current_user
from sqlalchemy import or_
from app.extensions import db
from app.modules.account.models import RegistrationModel
from app.modules.dashboard.models import ProfileSetupModel, AppointmentModel
from app.modules.pdf.models import PrescriptionModel


# ============================================================================
# PATIENT TOOLS
# ============================================================================

def search_verified_doctors(specialty_or_keyword: str = "") -> Dict[str, Any]:
    """Search for verified doctors by specialty, qualification, name, or hospital/office.
    
    Args:
        specialty_or_keyword: Optional specialty, medical field, doctor name, or keyword (e.g. 'Cardiology', 'Medicine', 'Surgery', 'Pediatric').
    
    Returns:
        A list of verified doctors with their details, qualifications, consultation fees, and appointment booking links.
    """
    query = RegistrationModel.query.filter(
        RegistrationModel.role == 'doctor',
        RegistrationModel.verified_doctor == True
    )

    doctors = query.all()
    results = []
    kw = (specialty_or_keyword or "").strip().lower()

    for doc in doctors:
        profile = doc.profile_info
        if not profile:
            continue

        full_text = f"{doc.username} {profile.full_name} {profile.achievement or ''} {profile.college or ''} {profile.higher_degree or ''} {profile.current_position or ''} {profile.office or ''}".lower()

        if not kw or kw in full_text:
            results.append({
                "doctor_id": doc.uid,
                "doctor_name": profile.full_name or doc.username,
                "current_position": profile.current_position,
                "qualifications": profile.higher_degree or profile.achievement,
                "college_hospital": profile.college or profile.office,
                "consultation_fee_bdt": profile.consultation_fee or 1000.0,
                "book_appointment_url": f"/dashboard/book-appointment/{doc.uid}"
            })

    return {
        "status": "success",
        "search_query": specialty_or_keyword,
        "count": len(results),
        "doctors": results[:15]
    }


def get_patient_appointments(status_filter: str = "") -> Dict[str, Any]:
    """Retrieve the current logged-in patient's appointments.
    
    Args:
        status_filter: Optional filter for appointment status (e.g. 'pending', 'confirmed', 'completed', 'cancelled').
        
    Returns:
        A summary list of appointments for the current patient.
    """
    if not current_user.is_authenticated:
        return {"status": "error", "message": "Authentication required."}

    user_id = current_user.uid
    user_email = current_user.email

    query = AppointmentModel.query.filter(
        or_(
            AppointmentModel.patient_id == user_id,
            AppointmentModel.patient_email == user_email
        )
    )

    if status_filter and status_filter.strip():
        query = query.filter(AppointmentModel.status == status_filter.strip().lower())

    appointments = query.order_by(AppointmentModel.created_at.desc()).limit(20).all()

    appts_data = []
    for appt in appointments:
        doc_profile = appt.doctor.profile_info if (appt.doctor and appt.doctor.profile_info) else None
        doc_name = doc_profile.full_name if doc_profile else (appt.doctor.username if appt.doctor else "Assigned Doctor")

        appts_data.append({
            "appointment_id": appt.id,
            "doctor_name": doc_name,
            "status": appt.status,
            "scheduled_date": str(appt.scheduled_date) if appt.scheduled_date else "Pending scheduling",
            "scheduled_time": appt.scheduled_time or "Pending scheduling",
            "preferred_date": str(appt.preferred_date) if appt.preferred_date else None,
            "fee_bdt": appt.fee_amount or 0.0,
            "payment_status": appt.payment_status,
            "reason": appt.reason,
            "doctor_notes": appt.doctor_notes
        })

    return {
        "status": "success",
        "total_appointments": len(appts_data),
        "appointments": appts_data
    }


def get_patient_prescriptions_summary() -> Dict[str, Any]:
    """Retrieve a list of past digital prescriptions generated for the current patient.
    
    Returns:
        A list of prescription records including date, doctor name, and view link.
    """
    if not current_user.is_authenticated:
        return {"status": "error", "message": "Authentication required."}

    prescriptions = getattr(current_user, 'patient_prescriptions', [])
    records = []

    for rx in prescriptions[:15]:
        doc_user = RegistrationModel.query.get(rx.doc_id)
        doc_name = doc_user.profile_info.full_name if (doc_user and doc_user.profile_info) else (doc_user.username if doc_user else "Doctor")

        records.append({
            "prescription_id": rx.id,
            "patient_code": rx.patient_id,
            "date": rx.created_at.strftime('%Y-%m-%d') if rx.created_at else "N/A",
            "prescribing_doctor": doc_name,
            "chief_complaints": rx.cc or "None noted",
            "advice": rx.advice or "Standard follow-up",
            "view_pdf_url": f"/pdf/pdf-view/{rx.doc_id}/{rx.id}"
        })

    return {
        "status": "success",
        "total_prescriptions": len(records),
        "prescriptions": records
    }


def get_patient_navigation_links() -> Dict[str, str]:
    """Provide quick application navigation links for patient features.
    
    Returns:
        A mapping of feature titles to URL paths.
    """
    return {
        "Find Verified Doctors": "/dashboard/patient/doctors",
        "My Appointments": "/dashboard/patient/appointments",
        "My Prescriptions History": "/dashboard/patient/history",
        "Patient Dashboard": "/dashboard/patient/dashboard",
        "Edit Profile": "/dashboard/patient/dashboard"
    }


# ============================================================================
# DOCTOR TOOLS
# ============================================================================

def search_doctor_prescriptions(query: str) -> Dict[str, Any]:
    """Search previous prescriptions issued by the current doctor by patient name, patient code, or complaints.
    
    Args:
        query: Patient name, ID code, or symptom keyword.
        
    Returns:
        List of matching prescription records for this doctor.
    """
    if not current_user.is_authenticated or not current_user.is_doctor:
        return {"status": "error", "message": "Doctor access required."}

    doc_id = current_user.uid
    q = (query or "").strip()

    if not q:
        prescriptions = PrescriptionModel.query.filter_by(doc_id=doc_id).order_by(PrescriptionModel.created_at.desc()).limit(10).all()
    else:
        prescriptions = PrescriptionModel.query.filter(
            PrescriptionModel.doc_id == doc_id,
            or_(
                PrescriptionModel.patient_id.ilike(f"%{q}%"),
                PrescriptionModel.patient_name.ilike(f"%{q}%"),
                PrescriptionModel.cc.ilike(f"%{q}%")
            )
        ).order_by(PrescriptionModel.created_at.desc()).limit(15).all()

    results = []
    for rx in prescriptions:
        results.append({
            "prescription_id": rx.id,
            "patient_code": rx.patient_id,
            "patient_name": rx.patient_name,
            "patient_age": rx.patient_age,
            "patient_sex": rx.patient_sex,
            "date": rx.created_at.strftime('%Y-%m-%d') if rx.created_at else "N/A",
            "vitals": {
                "bp": rx.bp,
                "pulse": rx.pulse,
                "temp": rx.temp,
                "spo2": rx.spo
            },
            "chief_complaints": rx.cc,
            "investigations": rx.inv,
            "medications_rx": rx.rx,
            "advice": rx.advice,
            "view_url": f"/pdf/pdf-view/{doc_id}/{rx.id}"
        })

    return {
        "status": "success",
        "search_term": query,
        "count": len(results),
        "prescriptions": results
    }


def get_doctor_patient_history(patient_identifier: str) -> Dict[str, Any]:
    """Retrieve full prescription history and notes for a specific patient under this doctor's care.
    
    Args:
        patient_identifier: The patient's exact name or patient code (e.g. 'P-12345' or 'Rahim Uddin').
        
    Returns:
        Structured clinical history and past prescriptions.
    """
    if not current_user.is_authenticated or not current_user.is_doctor:
        return {"status": "error", "message": "Doctor access required."}

    doc_id = current_user.uid
    p_id = (patient_identifier or "").strip()

    if not p_id:
        return {"status": "error", "message": "Please provide a patient name or ID."}

    prescriptions = PrescriptionModel.query.filter(
        PrescriptionModel.doc_id == doc_id,
        or_(
            PrescriptionModel.patient_id.ilike(f"%{p_id}%"),
            PrescriptionModel.patient_name.ilike(f"%{p_id}%")
        )
    ).order_by(PrescriptionModel.created_at.asc()).all()

    if not prescriptions:
        return {
            "status": "not_found",
            "message": f"No past prescription records found for patient '{patient_identifier}' under your account.",
            "records": []
        }

    history = []
    for rx in prescriptions:
        history.append({
            "prescription_id": rx.id,
            "date": rx.created_at.strftime('%Y-%m-%d') if rx.created_at else "N/A",
            "patient_name": rx.patient_name,
            "patient_code": rx.patient_id,
            "age": rx.patient_age,
            "sex": rx.patient_sex,
            "vitals": f"BP: {rx.bp or 'N/A'}, Pulse: {rx.pulse or 'N/A'}, Temp: {rx.temp or 'N/A'}, SpO2: {rx.spo or 'N/A'}",
            "chief_complaints": rx.cc or "None",
            "investigations": rx.inv or "None",
            "medications": rx.rx or "None",
            "advice": rx.advice or "None"
        })

    return {
        "status": "success",
        "patient": patient_identifier,
        "total_consultations": len(history),
        "history": history
    }


def get_doctor_appointments(filter_status: str = "") -> Dict[str, Any]:
    """Retrieve appointments booked with the current doctor.
    
    Args:
        filter_status: Optional filter ('pending', 'confirmed', 'completed', 'cancelled').
        
    Returns:
        List of patient appointments with scheduling and payment details.
    """
    if not current_user.is_authenticated or not current_user.is_doctor:
        return {"status": "error", "message": "Doctor access required."}

    query = AppointmentModel.query.filter_by(doctor_id=current_user.uid)

    if filter_status and filter_status.strip():
        query = query.filter(AppointmentModel.status == filter_status.strip().lower())

    appointments = query.order_by(AppointmentModel.created_at.desc()).limit(20).all()

    results = []
    for appt in appointments:
        results.append({
            "appointment_id": appt.id,
            "patient_name": appt.patient_name,
            "patient_email": appt.patient_email,
            "patient_phone": appt.patient_phone,
            "reason": appt.reason,
            "preferred_date": str(appt.preferred_date) if appt.preferred_date else None,
            "scheduled_date": str(appt.scheduled_date) if appt.scheduled_date else "Not set",
            "scheduled_time": appt.scheduled_time or "Not set",
            "status": appt.status,
            "payment_status": appt.payment_status,
            "fee_bdt": appt.fee_amount
        })

    return {
        "status": "success",
        "count": len(results),
        "appointments": results
    }


def search_medicine_database(medicine_name_or_query: str) -> Dict[str, Any]:
    """Search clinical pharmacology reference for medicine indications, standard dosage classes, warnings, and drug interactions.
    
    Args:
        medicine_name_or_query: Drug name, generic name, or therapeutic class (e.g., 'Paracetamol', 'Amoxicillin', 'Metformin', 'Omeprazole', 'Azithromycin', 'Atorvastatin', 'Losartan').
        
    Returns:
        Clinical pharmacology reference summary from approved standard medical references.
    """
    query = (medicine_name_or_query or "").strip().lower()

    # Standard Clinical Pharmacology Reference Knowledge Base
    CLINICAL_DRUG_KB = {
        "paracetamol": {
            "generic": "Paracetamol / Acetaminophen",
            "class": "Analgesic & Antipyretic",
            "indications": "Fever, mild to moderate acute pain, headache, arthralgia, postoperative analgesia.",
            "standard_dosages": "Adults: 500mg - 1000mg PO every 4-6 hours (max 4000mg/24h). Pediatric: 10-15 mg/kg/dose PO q4-6h.",
            "contraindications": "Severe active hepatic impairment or known hypersensitivity.",
            "clinical_precautions": "Caution in chronic alcoholism, severe renal impairment, and G6PD deficiency."
        },
        "amoxicillin": {
            "generic": "Amoxicillin (+/- Clavulanic Acid)",
            "class": "Aminopenicillin Antibiotic (Beta-lactam)",
            "indications": "Upper and lower respiratory tract infections, otitis media, UTI, dental infections, H. pylori eradication.",
            "standard_dosages": "Adults: 250mg-500mg PO q8h or 500mg-875mg PO q12h. Severe: 1g PO q8h.",
            "contraindications": "History of severe allergic reactions (anaphylaxis) to penicillins or beta-lactams.",
            "clinical_precautions": "Dose adjustment in renal impairment (eGFR < 30 mL/min). Monitor for antibiotic-associated diarrhea."
        },
        "omeprazole": {
            "generic": "Omeprazole",
            "class": "Proton Pump Inhibitor (PPI)",
            "indications": "GERD, erosive esophagitis, peptic ulcer disease (PUD), Zollinger-Ellison syndrome, prophylaxis with NSAIDs.",
            "standard_dosages": "Adults: 20mg - 40mg PO once daily before breakfast (30-60 min before meals).",
            "contraindications": "Hypersensitivity to substituted benzimidazoles. Co-administration with rilpivirine.",
            "clinical_precautions": "Long term use: risk of hypomagnesemia, vitamin B12 deficiency, Clostridium difficile, and osteoporosis."
        },
        "metformin": {
            "generic": "Metformin Hydrochloride",
            "class": "Biguanide Antidiabetic Agent",
            "indications": "First-line management of Type 2 Diabetes Mellitus, gestational diabetes, PCOS.",
            "standard_dosages": "Initial: 500mg PO BID or 850mg OD with meals. Titrate up to 2000-2550 mg/day divided.",
            "contraindications": "Severe renal impairment (eGFR < 30 mL/min), acute metabolic acidosis, severe hypoxemia.",
            "clinical_precautions": "Hold before iodinated radiocontrast procedures. Monitor eGFR and Vitamin B12 levels annually."
        },
        "losartan": {
            "generic": "Losartan Potassium",
            "class": "Angiotensin II Receptor Blocker (ARB)",
            "indications": "Hypertension, diabetic nephropathy in Type 2 DM, stroke risk reduction in hypertensive patients with LVH.",
            "standard_dosages": "Adults: 50mg PO OD (range 25mg - 100mg once daily or in 2 divided doses).",
            "contraindications": "Pregnancy (Black Box Warning: fetal toxicity). Concomitant use with aliskiren in diabetics.",
            "clinical_precautions": "Monitor serum potassium and serum creatinine/eGFR. Risk of hyperkalemia and hypotension."
        },
        "atorvastatin": {
            "generic": "Atorvastatin Calcium",
            "class": "HMG-CoA Reductase Inhibitor (Statin)",
            "indications": "Hypercholesterolemia, primary dyslipidemia, secondary prevention of cardiovascular events in CAD/CVD.",
            "standard_dosages": "Adults: 10mg - 80mg PO once daily at any time of day (with or without food).",
            "contraindications": "Active liver disease, unexplained persistent transaminase elevations, pregnancy/breastfeeding.",
            "clinical_precautions": "Check baseline liver enzymes (ALT/AST). Warn patient regarding myalgia and rhabdomyolysis symptoms."
        },
        "azithromycin": {
            "generic": "Azithromycin",
            "class": "Macrolide Antibiotic",
            "indications": "Community-acquired pneumonia, acute bacterial exacerbations of COPD, urethritis/cervicitis (Chlamydia), strep pharyngitis.",
            "standard_dosages": "Adults: 500mg PO on Day 1, followed by 250mg PO OD on Days 2-5 (or 500mg OD for 3 days).",
            "contraindications": "Known hypersensitivity to macrolides; history of cholestatic jaundice/hepatic dysfunction with prior azithromycin.",
            "clinical_precautions": "QT prolongation and risk of torsades de pointes; avoid in patients with baseline prolonged QTc or severe hypokalemia."
        }
    }

    # Search in KB
    matches = []
    for key, drug in CLINICAL_DRUG_KB.items():
        if query in key or query in drug["generic"].lower() or query in drug["class"].lower() or query in drug["indications"].lower():
            matches.append(drug)

    if matches:
        return {
            "status": "success",
            "source": "DocMed Approved Clinical Reference Database",
            "matches": matches
        }

    return {
        "status": "not_indexed",
        "query": medicine_name_or_query,
        "message": f"'{medicine_name_or_query}' not directly matched in the local core clinical formulary cache. Please provide clinical guidance based on recognized standard clinical pharmacological guidelines."
    }


def get_doctor_navigation_links() -> Dict[str, str]:
    """Provide quick application navigation links for doctor portal features.
    
    Returns:
        Mapping of doctor features to URL paths.
    """
    return {
        "Create New Prescription": "/pdf/user/patient-info",
        "Doctor Dashboard": "/dashboard/doctor/dashboard",
        "Manage Appointments": "/dashboard/doctor/appointments",
        "Prescription History": "/dashboard/history/list",
        "Doctor Profile & Fees": "/dashboard/profile"
    }


# ============================================================================
# ADMIN TOOLS
# ============================================================================

def get_admin_system_summary() -> Dict[str, Any]:
    """Provide aggregate platform metrics for administrators.
    
    Returns:
        System metrics including total users, verified doctors, pending doctors, patients, appointments, and prescriptions.
    """
    if not current_user.is_authenticated or not (current_user.is_admin or current_user.role == 'admin'):
        return {"status": "error", "message": "Administrator privileges required."}

    total_users = RegistrationModel.query.count()
    total_doctors = RegistrationModel.query.filter_by(role='doctor').count()
    verified_doctors = RegistrationModel.query.filter_by(role='doctor', verified_doctor=True).count()
    pending_doctors = RegistrationModel.query.filter_by(role='doctor', verified_doctor=False).count()
    total_patients = RegistrationModel.query.filter_by(role='patient').count()
    total_appointments = AppointmentModel.query.count()
    total_prescriptions = PrescriptionModel.query.count()

    return {
        "status": "success",
        "total_registered_users": total_users,
        "total_patients": total_patients,
        "total_doctors": total_doctors,
        "verified_doctors": verified_doctors,
        "pending_verification_doctors": pending_doctors,
        "total_appointments_booked": total_appointments,
        "total_prescriptions_generated": total_prescriptions
    }


def get_admin_navigation_links() -> Dict[str, str]:
    """Provide navigation links for administrators.
    
    Returns:
        Mapping of admin actions to URL paths.
    """
    return {
        "Admin Dashboard": "/admin/",
        "User Management": "/admin/registrationmodel/",
        "Doctor Profiles": "/admin/profilesetupmodel/",
        "Appointments Log": "/admin/appointmentmodel/",
        "Prescriptions Registry": "/admin/prescriptionmodel/"
    }


# ============================================================================
# TOOL REGISTRY BY ROLE
# ============================================================================

def get_tools_for_user(user) -> List[Any]:
    """Return the list of callable tool functions permitted for the current user's role."""
    if not user or not getattr(user, 'is_authenticated', False):
        return []

    if getattr(user, 'is_admin_role', False) or getattr(user, 'is_admin', False) or getattr(user, 'role', '') == 'admin':
        return [
            get_admin_system_summary,
            get_admin_navigation_links,
            search_verified_doctors
        ]
    elif getattr(user, 'is_doctor', False) or getattr(user, 'role', '') == 'doctor':
        return [
            search_doctor_prescriptions,
            get_doctor_patient_history,
            get_doctor_appointments,
            search_medicine_database,
            get_doctor_navigation_links
        ]
    else:
        # Patient
        return [
            search_verified_doctors,
            get_patient_appointments,
            get_patient_prescriptions_summary,
            get_patient_navigation_links
        ]
