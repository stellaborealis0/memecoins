# Nuevo archivo: memecoins/agents/dexter_validator.py
from typing import Dict, List, Any
from dataclasses import dataclass
import logging
from datetime import datetime
import json

@dataclass
class ValidationResult:
    is_valid: bool
    confidence_score: float
    validation_steps: List[str]
    recommendations: List[str]
    validation_details: Dict[str, Any]

class DexterValidator:
    def __init__(self, memory_system):
        self.memory_system = memory_system
        self.logger = logging.getLogger(__name__)
        self.validation_threshold = 0.7
        self.max_validation_attempts = 3
    
    def validate_action(self, action: Dict[str, Any], context: Dict[str, Any]) -> ValidationResult:
        """
        Valida una acción antes de ejecutarla siguiendo el patrón Plan/Act/Validate/Answer
        """
        try:
            # Plan phase - Validar el plan de acción
            plan_validation = self._validate_plan(action, context)
            
            # Act phase - Validar la viabilidad de la acción
            action_validation = self._validate_action_feasibility(action, context)
            
            # Validate phase - Validar la coherencia con objetivos
            coherence_validation = self._validate_coherence(action, context)
            
            # Calculate overall validation score
            validation_score = self._calculate_validation_score([
                plan_validation, action_validation, coherence_validation
            ])
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                action, context, plan_validation, action_validation, coherence_validation
            )
            
            # Log validation for memory system
            self._log_validation(action, validation_score, recommendations)
            
            return ValidationResult(
                is_valid=validation_score > self.validation_threshold,
                confidence_score=validation_score,
                validation_steps=[plan_validation, action_validation, coherence_validation],
                recommendations=recommendations,
                validation_details={
                    'plan_score': plan_validation.get('score', 0),
                    'action_score': action_validation.get('score', 0),
                    'coherence_score': coherence_validation.get('score', 0),
                    'timestamp': datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            self.logger.error(f"Validation error: {str(e)}")
            return ValidationResult(
                is_valid=False,
                confidence_score=0.0,
                validation_steps=[f"Error during validation: {str(e)}"],
                recommendations=["Retry validation", "Check action parameters"],
                validation_details={'error': str(e), 'timestamp': datetime.now().isoformat()}
            )
    
    def _validate_plan(self, action: Dict, context: Dict) -> Dict[str, Any]:
        """Valida el plan de acción"""
        plan_checks = {
            'has_clear_objective': 'objective' in action,
            'has_timeframe': 'deadline' in action or 'duration' in action,
            'has_resources': 'resources' in action or 'budget' in action,
            'aligns_with_goals': self._check_goal_alignment(action, context),
            'risk_assessed': 'risk_level' in action or 'risk_assessment' in action
        }
        
        score = sum(1 for check in plan_checks.values() if check) / len(plan_checks)
        
        return {
            'step': 'plan_validation',
            'checks': plan_checks,
            'score': score,
            'passed': score >= 0.6,
            'issues': [k for k, v in plan_checks.items() if not v]
        }
    
    def _validate_action_feasibility(self, action: Dict, context: Dict) -> Dict[str, Any]:
        """Valida la viabilidad de la acción"""
        feasibility_checks = {
            'resources_available': self._check_resource_availability(action, context),
            'time_realistic': self._check_time_realistic(action, context),
            'technical_feasible': self._check_technical_feasibility(action, context),
            'within_budget': self._check_budget_constraints(action, context),
            'permissions_granted': self._check_permissions(action, context)
        }
        
        score = sum(1 for check in feasibility_checks.values() if check) / len(feasibility_checks)
        
        return {
            'step': 'feasibility_validation',
            'checks': feasibility_checks,
            'score': score,
            'passed': score >= 0.7,
            'issues': [k for k, v in feasibility_checks.items() if not v]
        }
    
    def _validate_coherence(self, action: Dict, context: Dict) -> Dict[str, Any]:
        """Valida la coherencia con objetivos y contexto"""
        coherence_checks = {
            'aligns_with_strategy': self._check_strategy_alignment(action, context),
            'consistent_with_history': self._check_consistency_with_history(action, context),
            'logical_sequence': self._check_logical_sequence(action, context),
            'no_conflicts': self._check_no_conflicts(action, context),
            'supports_overall_goals': self._check_supports_overall_goals(action, context)
        }
        
        score = sum(1 for check in coherence_checks.values() if check) / len(coherence_checks)
        
        return {
            'step': 'coherence_validation',
            'checks': coherence_checks,
            'score': score,
            'passed': score >= 0.8,
            'issues': [k for k, v in coherence_checks.items() if not v]
        }
    
    def _calculate_validation_score(self, validation_results: List[Dict]) -> float:
        """Calcula el score de validación combinado"""
        if not validation_results:
            return 0.0
        
        total_weighted_score = 0
        weights = [0.4, 0.3, 0.3]  # Plan, Feasibility, Coherence weights
        
        for i, result in enumerate(validation_results):
            weight = weights[i] if i < len(weights) else 1.0/len(validation_results)
            total_weighted_score += result.get('score', 0) * weight
        
        return min(total_weighted_score, 1.0)
    
    def _generate_recommendations(self, action: Dict, context: Dict, 
                                plan_val: Dict, action_val: Dict, coherence_val: Dict) -> List[str]:
        """Genera recomendaciones basadas en las validaciones"""
        recommendations = []
        
        # Recommendations based on plan validation
        if not plan_val['passed']:
            recommendations.extend([
                "Clarify action objectives",
                "Define clear success metrics",
                "Establish realistic timeline",
                "Assess and document risks"
            ])
        
        # Recommendations based on feasibility validation
        if not action_val['passed']:
            recommendations.extend([
                "Verify resource availability",
                "Adjust timeline if needed",
                "Check technical requirements",
                "Review budget constraints"
            ])
        
        # Recommendations based on coherence validation
        if not coherence_val['passed']:
            recommendations.extend([
                "Align with strategic goals",
                "Check for conflicts with existing plans",
                "Ensure logical sequence of actions",
                "Validate consistency with past decisions"
            ])
        
        # Specific recommendations based on issues
        all_issues = plan_val['issues'] + action_val['issues'] + coherence_val['issues']
        if 'risk_assessed' in all_issues:
            recommendations.append("Conduct thorough risk assessment")
        if 'resources_available' in all_issues:
            recommendations.append("Secure necessary resources")
        if 'aligns_with_strategy' in all_issues:
            recommendations.append("Review strategic alignment")
        
        return list(set(recommendations))  # Remove duplicates
    
    def _check_goal_alignment(self, action: Dict, context: Dict) -> bool:
        """Verifica alineación con objetivos"""
        if 'objective' not in action:
            return False
        return True  # Implementar lógica específica según tu dominio
    
    def _check_resource_availability(self, action: Dict, context: Dict) -> bool:
        """Verifica disponibilidad de recursos"""
        if 'resources' in action:
            # Implementar lógica de verificación de recursos
            return True
        return True  # Por defecto, asumir disponible
    
    def _check_time_realistic(self, action: Dict, context: Dict) -> bool:
        """Verifica si el tiempo es realista"""
        if 'duration' in action:
            duration = action['duration']
            # Implementar lógica de verificación de duración
            return True
        return True
    
    def _check_technical_feasibility(self, action: Dict, context: Dict) -> bool:
        """Verifica factibilidad técnica"""
        # Implementar lógica de verificación técnica
        return True
    
    def _check_budget_constraints(self, action: Dict, context: Dict) -> bool:
        """Verifica restricciones de presupuesto"""
        if 'cost' in action and 'budget' in context:
            return action['cost'] <= context['budget']
        return True
    
    def _check_permissions(self, action: Dict, context: Dict) -> bool:
        """Verifica permisos necesarios"""
        # Implementar lógica de verificación de permisos
        return True
    
    def _check_strategy_alignment(self, action: Dict, context: Dict) -> bool:
        """Verifica alineación con estrategia"""
        # Implementar lógica de alineación estratégica
        return True
    
    def _check_consistency_with_history(self, action: Dict, context: Dict) -> bool:
        """Verifica consistencia con historia"""
        # Consultar sistema de memoria para verificar consistencia
        if self.memory_system:
            past_similar_actions = self.memory_system.recall_context(
                query=json.dumps(action.get('objective', '')),
                context_tags=['decision', 'action']
            )
            # Implementar lógica de verificación de consistencia
            return True
        return True
    
    def _check_logical_sequence(self, action: Dict, context: Dict) -> bool:
        """Verifica secuencia lógica"""
        # Implementar lógica de verificación de secuencia
        return True
    
    def _check_no_conflicts(self, action: Dict, context: Dict) -> bool:
        """Verifica ausencia de conflictos"""
        # Implementar lógica de verificación de conflictos
        return True
    
    def _check_supports_overall_goals(self, action: Dict, context: Dict) -> bool:
        """Verifica soporte a objetivos generales"""
        # Implementar lógica de verificación de apoyo a objetivos
        return True
    
    def _log_validation(self, action: Dict, score: float, recommendations: List[str]):
        """Registra la validación en el sistema de memoria"""
        if self.memory_system:
            validation_record = {
                'action': action,
                'validation_score': score,
                'recommendations': recommendations,
                'timestamp': datetime.now().isoformat()
            }
            
            self.memory_system.store_interaction(
                content=json.dumps(validation_record),
                interaction_type='validation',
                importance=min(score, 0.9),  # No guardar validaciones muy bajas
                tags=['validation', 'dexter', 'quality_control']
            )
    
    def validate_behavior_consistency(self, current_behavior: str, 
                                   expected_behavior: str = None) -> Dict[str, Any]:
        """Valida la consistencia del comportamiento del agente"""
        if not self.memory_system:
            return {'consistency_score': 1.0, 'drift_detected': False, 'recommendations': []}
        
        # Recuperar comportamientos históricos
        past_behaviors = self.memory_system.recall_context(
            query=current_behavior,
            context_tags=['behavior', 'decision', 'action'],
            time_window=timedelta(hours=24)
        )
        
        consistency_score = 0.0
        drift_detected = False
        
        if past_behaviors.get('similar_memories'):
            # Comparar con comportamientos pasados
            recent_behavior = past_behaviors['similar_memories'][0]
            # Implementar lógica de comparación de comportamiento
            similarity = self._calculate_behavior_similarity(
                current_behavior, recent_behavior.content
            )
            consistency_score = similarity
            drift_detected = similarity < 0.7
        
        recommendations = []
        if drift_detected:
            recommendations.append("Review agent behavior patterns")
            recommendations.append("Align with established decision patterns")
            recommendations.append("Consider retraining if drift persists")
        else:
            recommendations.append("Behavior remains consistent with historical patterns")
        
        return {
            'consistency_score': consistency_score,
            'drift_detected': drift_detected,
            'recommendations': recommendations,
            'past_behaviors_count': len(past_behaviors.get('similar_memories', []))
        }
    
    def _calculate_behavior_similarity(self, behavior1: str, behavior2: str) -> float:
        """Calcula similitud entre comportamientos"""
        # Implementar lógica de cálculo de similitud
        # Por ahora, usar una métrica simple basada en palabras clave
        words1 = set(behavior1.lower().split())
        words2 = set(behavior2.lower().split())
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0

# Función auxiliar para crear validator
def create_dexter_validator(memory_system):
    """Crea una instancia de DexterValidator con el sistema de memoria dado"""
    return DexterValidator(memory_system)

if __name__ == "__main__":
    # Ejemplo de uso
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    
    # Importar sistema de memoria (si está disponible)
    try:
        from ..persistent_memory_hermes import HermesMemorySystem
        memory_system = HermesMemorySystem()
    except ImportError:
        memory_system = None
    
    validator = DexterValidator(memory_system)
    
    # Ejemplo de validación
    test_action = {
        'objective': 'Analyze market trends for cryptocurrency investments',
        'resources': ['API access', 'computational power'],
        'duration': '2 hours',
        'risk_level': 'low',
        'budget': 1000
    }
    
    test_context = {
        'current_market_conditions': 'volatile',
        'risk_tolerance': 'medium',
        'available_capital': 50000
    }
    
    result = validator.validate_action(test_action, test_context)
    print(f"Validation result: {result.is_valid}")
    print(f"Confidence score: {result.confidence_score}")
    print(f"Recommendations: {result.recommendations}")