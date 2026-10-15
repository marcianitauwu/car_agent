"""Contratos estrictos para las decisiones de las llamadas a modelos."""
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator

AgentKey = Literal['comfort', 'consumption', 'economy']

'''
    allowed	--> Solicitud permitida.
    off_topic --> Pregunta fuera del tema de vehículos.
    code_request --> Solicitud de código que la política puede restringir.
    prompt_injection --> Intento de alterar las instrucciones del sistema.
    secrets	--> Solicitud relacionada con credenciales o secretos.
    privacy	--> Solicitud que puede comprometer información privada.
    external_source	--> Solicitud de información fuera de las fuentes autorizadas.
    unsafe_output	--> Contenido identificado como inseguro.
    unknown	--> No se pudo clasificar adecuadamente.
'''

PolicyCategory = Literal[
    
    
    'allowed', 'off_topic', 'code_request', 'prompt_injection',
    'secrets', 'privacy', 'external_source', 'unsafe_output', 'unknown',
]


class ChatRequest(BaseModel):
    message: str = Field(min_length=3, max_length=700)


class ApprovedQuestion(BaseModel):
    question: str

class PolicyDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    allowed: bool
    category: PolicyCategory
    refined_question: str | None = Field(default=None, min_length=3, max_length=700)

    @field_validator('category')
    @classmethod
    def category_compatible(cls, value: str, info):
        allowed = info.data.get('allowed')
        if allowed is True and value != 'allowed':
            raise ValueError('decision inconsistente')
        if allowed is False and value == 'allowed':
            raise ValueError('decision inconsistente')
        return value


class PolicyReview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    approved: bool
    category: PolicyCategory
    reason_code: Literal['none', 'unsupported_claim', 'contradictory_evidence',
                         'invalid_citation', 'criteria_mismatch', 'unsafe_content',
                         'instruction_injection', 'invalid_review', 'unspecified'] = 'unspecified'
    affected_agents: list[Literal['comfort', 'consumption', 'economy', 'synthesizer']] = Field(default_factory=list)


SearchField = Literal['marca', 'modelo', 'tipo_carroceria', 'combustible',
                      'transmision', 'traccion', 'condicion', 'color', 'ciudad',
                      'pais', 'anio', 'cilindrada_litros', 'consumo_l_100km',
                      'autonomia_electrica_km', 'precio_usd', 'kilometraje_km',
                      'numero_puertas', 'numero_asientos', 'disponible', 'caracteristicas']
NumericSearchField = Literal['anio', 'cilindrada_litros', 'consumo_l_100km',
                            'autonomia_electrica_km', 'precio_usd', 'kilometraje_km',
                            'numero_puertas', 'numero_asientos']

# Definir filtros de búsqueda con validación estricta para cada campo y operador
class SearchConstraint(BaseModel):
    model_config = ConfigDict(extra='forbid')
    field: SearchField
    
    ''' eq	Igual a
        ne	Diferente de	
        lt	Menor que	
        le	Menor o igual	
        gt	Mayor que	
        ge	Mayor o igual
    '''
    
    operator: Literal['eq', 'ne', 'lt', 'le', 'gt', 'ge']
    value: str | float | bool

    @field_validator('value')
    @classmethod
    def typed_value(cls, value, info):
        field = info.data.get('field')
        numeric = {'anio', 'cilindrada_litros', 'consumo_l_100km',
                   'autonomia_electrica_km', 'precio_usd', 'kilometraje_km',
                   'numero_puertas', 'numero_asientos'}
        import math
        if field in numeric:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('Se requiere un número finito')
        elif field == 'disponible':
            if not isinstance(value, bool):
                raise ValueError('Se requiere booleano')
        elif not isinstance(value, str) or not 1 <= len(value) <= 100:
            raise ValueError('Se requiere texto corto')
        if field not in numeric and info.data.get('operator') not in ('eq', 'ne'):
            raise ValueError('Operador incompatible')
        return value

class SearchOrder(BaseModel):
    model_config = ConfigDict(extra='forbid')
    field: NumericSearchField
    direction: Literal['asc', 'desc']

# Construir plan de búsqueda
class SearchPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')

    search_text: str = Field(
        min_length=1,
        max_length=700
    )

    search_mode: Literal[
        'semantic',
        'structured'
    ] = 'semantic'

    filter_groups: list[list[SearchConstraint]] = Field(
        default_factory=list,
        max_length=20
    )

    order_by: list[SearchOrder] = Field(
        default_factory=list,
        max_length=3
    )

    select_fields: list[SearchField] = Field(
        default_factory=list,
        max_length=20
    )
        
    @field_validator('filter_groups')
    @classmethod
    def bounded_groups(cls, groups):
        if any(not 1 <= len(group) <= 10 for group in groups):
            raise ValueError('Grupo de filtros vacío o demasiado grande')
        return groups


class RoutingDecision(BaseModel):
    question: str
    agents: list[AgentKey] = Field(min_length=1, max_length=2)
    reason: str = Field(max_length=180)
    search_plans: dict[AgentKey, SearchPlan] = Field(default_factory=dict)

    @field_validator('agents')
    @classmethod
    def unique_agents(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError('Agentes duplicados')
        return value


class SpecialistResult(BaseModel):
    """Mensaje interno hacia el ejecutor que reúne la ruta seleccionada."""
    question: str
    selected_agents: list[AgentKey]
    agent: AgentKey
    answer: str
    documents: list[dict]
    invalid: str | None = None
