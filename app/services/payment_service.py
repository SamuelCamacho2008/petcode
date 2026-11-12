import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from app.models.payment import RewardPayment, PaymentStatus
from app.models.account import ADMIN_EMAIL

class PaymentService:
    """
    Servicio de gestión de recompensas y garantía Escrow para PetCode.
    - Comisión de plataforma PetCode: 5% (0.05)
    - Pago neto para el rescatista: 95% (0.95)
    Supervisado por el Administrador: samuelcamachoaguirre4@gmail.com
    """
    PLATFORM_COMMISSION_RATE = 0.05
    RESCUER_PAYOUT_RATE = 0.95

    @classmethod
    def calculate_split(cls, total_amount: float) -> Tuple[float, float]:
        """
        Calcula el desglose del 5% para PetCode y el 95% para el rescatista.
        """
        fee = round(total_amount * cls.PLATFORM_COMMISSION_RATE, 2)
        payout = round(total_amount * cls.RESCUER_PAYOUT_RATE, 2)
        # Ajuste de centavos si aplica
        if fee + payout != total_amount:
            payout = total_amount - fee
        return fee, payout

    @classmethod
    def get_financial_analytics(cls, payments: List[RewardPayment]) -> dict:
        """
        Genera el informe de ganancias para el panel de administración.
        """
        total_escrow = sum(p.total_reward for p in payments if p.status == PaymentStatus.ESCROW)
        total_released = sum(p.total_reward for p in payments if p.status == PaymentStatus.RELEASED)
        platform_earnings_collected = sum(p.platform_fee for p in payments if p.status == PaymentStatus.RELEASED)
        platform_earnings_pending = sum(p.platform_fee for p in payments if p.status == PaymentStatus.ESCROW)
        rescuer_payouts_completed = sum(p.rescuer_payout for p in payments if p.status == PaymentStatus.RELEASED)
        rescuer_payouts_pending = sum(p.rescuer_payout for p in payments if p.status == PaymentStatus.ESCROW)
        active_escrows = sum(1 for p in payments if p.status == PaymentStatus.ESCROW)
        completed_escrows = sum(1 for p in payments if p.status == PaymentStatus.RELEASED)

        return {
            "platform_fee_percent": 5.0,
            "rescuer_payout_percent": 95.0,
            "total_transactions": len(payments),
            "total_volume": total_escrow + total_released,
            "escrow_volume": total_escrow,
            "released_volume": total_released,
            "total_escrow_active": total_escrow,
            "total_rewards_paid": total_released,
            "platform_earnings_collected": platform_earnings_collected,
            "platform_earnings_pending": platform_earnings_pending,
            "platform_earnings_5_percent": platform_earnings_collected,
            "rescuer_payouts_completed": rescuer_payouts_completed,
            "rescuer_payouts_pending": rescuer_payouts_pending,
            "rescuer_payouts_95_percent": rescuer_payouts_completed,
            "active_escrows": active_escrows,
            "completed_escrows": completed_escrows,
            "admin_contact": ADMIN_EMAIL
        }

payment_service = PaymentService()
