import gradio as gr
import torch
from typing import Optional, Dict, List
from pydantic import BaseModel, Field, field_validator
from gradio_i18n import Translate, gettext as _
from enum import Enum
import yaml

from modules.utils.constants import AUTOMATIC_DETECTION


class WhisperImpl(Enum):
    WHISPER = "whisper"
    FASTER_WHISPER = "faster-whisper"
    INSANELY_FAST_WHISPER = "insanely_fast_whisper"


class VadParams(BaseModel):
    """Voice Activity Detection parameters"""
    vad_filter: bool = Field(default=False, description="Enable voice activity detection to filter out non-speech parts")
    threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Speech threshold for Silero VAD. Probabilities above this value are considered speech"
    )
    min_speech_duration_ms: int = Field(
        default=250,
        ge=0,
        description="Final speech chunks shorter than this are discarded"
    )
    max_speech_duration_s: float = Field(
        default=float("inf"),
        gt=0,
        description="Maximum duration of speech chunks in seconds"
    )
    min_silence_duration_ms: int = Field(
        default=2000,
        ge=0,
        description="Minimum silence duration between speech chunks"
    )
    speech_pad_ms: int = Field(
        default=400,
        ge=0,
        description="Padding added to each side of speech chunks"
    )

    def to_dict(self) -> Dict:
        return self.model_dump()

    @classmethod
    def to_gradio_inputs(cls, defaults: Optional[Dict] = None) -> List[gr.components.base.FormComponent]:
        defaults = defaults or {}
        return [
            gr.Checkbox(label=_("Enable Silero VAD Filter"), value=defaults.get("vad_filter", cls.vad_filter),
                        interactive=True,
                        info=_("Enable this to transcribe only detected voice")),
            gr.Slider(minimum=0.0, maximum=1.0, step=0.01, label="Speech Threshold",
                      value=defaults.get("threshold", cls.threshold),
                      info="Lower it to be more sensitive to small sounds."),
            gr.Number(label="Minimum Speech Duration (ms)", precision=0,
                      value=defaults.get("min_speech_duration_ms", cls.min_speech_duration_ms),
                      info="Final speech chunks shorter than this time are thrown out"),
            gr.Number(label="Maximum Speech Duration (s)",
                      value=defaults.get("max_speech_duration_s", cls.max_speech_duration_s),
                      info="Maximum duration of speech chunks in \"seconds\"."),
            gr.Number(label="Minimum Silence Duration (ms)", precision=0,
                      value=defaults.get("min_silence_duration_ms", cls.min_silence_duration_ms),
                      info="In the end of each speech chunk wait for this time"
                            " before separating it"),
            gr.Number(label="Speech Padding (ms)", precision=0,
                      value=defaults.get("speech_pad_ms", cls.speech_pad_ms),
                      info="Final speech chunks are padded by this time each side")
        ]



class DiarizationParams(BaseModel):
    """Speaker diarization parameters"""
    is_diarize: bool = Field(default=False, description="Enable speaker diarization")
    hf_token: str = Field(
        default="",
        description="Hugging Face token for downloading diarization models"
    )

    def to_dict(self) -> Dict:
        return self.model_dump()

    @classmethod
    def to_gradio_inputs(cls,
                         defaults: Optional[Dict] = None,
                         available_devices: Optional[List] = None,
                         device: Optional[str] = None) -> List[gr.components.base.FormComponent]:
        defaults = defaults or {}
        return [
            gr.Checkbox(
                label=_("Enable Diarization"),
                value=defaults.get("is_diarize", cls.is_diarize),
                info=_("Enable speaker diarization")
            ),
            gr.Textbox(
                label=_("HuggingFace Token"),
                value=defaults.get("hf_token", cls.hf_token),
                info=_("This is only needed the first time you download the model")
            ),
            gr.Dropdown(
                label=_("Device"),
                choices=["cpu", "cuda"] if available_devices is None else available_devices,
                value="cuda" if device is None else device,
                info=_("Device to run diarization model")
            )
        ]


class BGMSeparationParams(BaseModel):
    """Background music separation parameters"""
    is_separate_bgm: bool = Field(default=False, description="Enable background music separation")
    model_size: str = Field(
        default="UVR-MDX-NET-Inst_HQ_4",
        description="UVR model size"
    )
    segment_size: int = Field(
        default=256,
        gt=0,
        description="Segment size for UVR model"
    )
    save_file: bool = Field(
        default=False,
        description="Whether to save separated audio files"
    )
    enable_offload: bool = Field(
        default=True,
        description="Offload UVR model after transcription"
    )

    def to_dict(self) -> Dict:
        return self.model_dump()

    @classmethod
    def to_gradio_input(cls,
                        defaults: Optional[Dict] = None,
                        available_devices: Optional[List] = None,
                        device: Optional[str] = None,
                        available_models: Optional[List] = None) -> List[gr.components.base.FormComponent]:
        defaults = defaults or {}
        return [
            gr.Checkbox(
                label=_("Enable Background Music Remover Filter"),
                value=defaults.get("is_separate_bgm", cls.is_separate_bgm),
                interactive=True,
                info=_("Enabling this will remove background music")
            ),
            gr.Dropdown(
                label=_("Device"),
                choices=["cpu", "cuda"] if available_devices is None else available_devices,
                value="cuda" if device is None else device,
                info=_("Device to run UVR model")
            ),
            gr.Dropdown(
                label=_("Model"),
                choices=["UVR-MDX-NET-Inst_HQ_4", "UVR-MDX-NET-Inst_3"] if available_models is None else available_models,
                value=defaults.get("model_size", cls.model_size),
                info=_("UVR model size")
            ),
            gr.Number(
                label="Segment Size",
                value=defaults.get("segment_size", cls.segment_size),
                precision=0,
                info="Segment size for UVR model"
            ),
            gr.Checkbox(
                label=_("Save separated files to output"),
                value=defaults.get("save_file", cls.save_file),
                info=_("Whether to save separated audio files")
            ),
            gr.Checkbox(
                label=_("Offload sub model after removing background music"),
                value=defaults.get("enable_offload", cls.enable_offload),
                info=_("Offload UVR model after transcription")
            )
        ]


class WhisperParams(BaseModel):
    """Whisper parameters"""
    model_size: str = Field(default="large-v2", description="Whisper model size")
    lang: Optional[str] = Field(default=None, description="Source language of the file to transcribe")
    is_translate: bool = Field(default=False, description="Translate speech to English end-to-end")
    beam_size: int = Field(default=5, ge=1, description="Beam size for decoding")
    log_prob_threshold: float = Field(
        default=-1.0,
        description="Threshold for average log probability of sampled tokens"
    )
    no_speech_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Threshold for detecting silence"
    )
    compute_type: str = Field(default="float16", description="Computation type for transcription")
    best_of: int = Field(default=5, ge=1, description="Number of candidates when sampling")
    patience: float = Field(default=1.0, gt=0, description="Beam search patience factor")
    condition_on_previous_text: bool = Field(
        default=True,
        description="Use previous output as prompt for next window"
    )
    prompt_reset_on_temperature: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Temperature threshold for resetting prompt"
    )
    initial_prompt: Optional[str] = Field(default=None, description="Initial prompt for first window")
    temperature: float = Field(
        default=0.0,
        ge=0.0,
        description="Temperature for sampling"
    )
    compression_ratio_threshold: float = Field(
        default=2.4,
        gt=0,
        description="Threshold for gzip compression ratio"
    )
    batch_size: int = Field(default=24, gt=0, description="Batch size for processing")
    length_penalty: float = Field(default=1.0, gt=0, description="Exponential length penalty")
    repetition_penalty: float = Field(default=1.0, gt=0, description="Penalty for repeated tokens")
    no_repeat_ngram_size: int = Field(default=0, ge=0, description="Size of n-grams to prevent repetition")
    prefix: Optional[str] = Field(default=None, description="Prefix text for first window")
    suppress_blank: bool = Field(
        default=True,
        description="Suppress blank outputs at start of sampling"
    )
    suppress_tokens: Optional[str] = Field(default="[-1]", description="Token IDs to suppress")
    max_initial_timestamp: float = Field(
        default=0.0,
        ge=0.0,
        description="Maximum initial timestamp"
    )
    word_timestamps: bool = Field(default=False, description="Extract word-level timestamps")
    prepend_punctuations: Optional[str] = Field(
        default="\"'“¿([{-",
        description="Punctuations to merge with next word"
    )
    append_punctuations: Optional[str] = Field(
        default="\"'.。,，!！?？:：”)]}、",
        description="Punctuations to merge with previous word"
    )
    max_new_tokens: Optional[int] = Field(default=None, description="Maximum number of new tokens per chunk")
    chunk_length: Optional[int] = Field(default=30, description="Length of audio segments in seconds")
    hallucination_silence_threshold: Optional[float] = Field(
        default=None,
        description="Threshold for skipping silent periods in hallucination detection"
    )
    hotwords: Optional[str] = Field(default=None, description="Hotwords/hint phrases for the model")
    language_detection_threshold: Optional[float] = Field(
        default=None,
        description="Threshold for language detection probability"
    )
    language_detection_segments: int = Field(
        default=1,
        gt=0,
        description="Number of segments for language detection"
    )

    def to_dict(self):
        return self.model_dump()

    @field_validator('lang')
    def validate_lang(cls, v):
        from modules.utils.constants import AUTOMATIC_DETECTION
        return None if v == AUTOMATIC_DETECTION.unwrap() else v

    @classmethod
    def to_gradio_inputs(cls,
                         defaults: Optional[Dict] = None,
                         only_advanced: Optional[bool] = True,
                         whisper_type: Optional[WhisperImpl] = None,
                         available_compute_types: Optional[List] = None,
                         compute_type: Optional[str] = None):
        defaults = {} if defaults is None else defaults
        whisper_type = WhisperImpl.FASTER_WHISPER if whisper_type is None else whisper_type

        inputs = []
        if not only_advanced:
            inputs += [
                gr.Dropdown(
                    label="Model Size",
                    choices=["small", "medium", "large-v2"],
                    value=defaults.get("model_size", cls.model_size),
                    info="Whisper model size"
                ),
                gr.Textbox(
                    label="Language",
                    value=defaults.get("lang", cls.lang),
                    info="Source language of the file to transcribe"
                ),
                gr.Checkbox(
                    label="Translate to English",
                    value=defaults.get("is_translate", cls.is_translate),
                    info="Translate speech to English end-to-end"
                ),
            ]

        inputs += [
            gr.Number(
                label="Beam Size",
                value=defaults.get("beam_size", cls.beam_size),
                precision=0,
                info="Beam size for decoding"
            ),
            gr.Number(
                label="Log Probability Threshold",
                value=defaults.get("log_prob_threshold", cls.log_prob_threshold),
                info="Threshold for average log probability of sampled tokens"
            ),
            gr.Number(
                label="No Speech Threshold",
                value=defaults.get("no_speech_threshold", cls.no_speech_threshold),
                info="Threshold for detecting silence"
            ),
            gr.Dropdown(
                label="Compute Type",
                choices=["float16", "int8", "int16"] if available_compute_types is None else available_compute_types,
                value=defaults.get("compute_type", compute_type),
                info="Computation type for transcription"
            ),
            gr.Number(
                label="Best Of",
                value=defaults.get("best_of", cls.best_of),
                precision=0,
                info="Number of candidates when sampling"
            ),
            gr.Number(
                label="Patience",
                value=defaults.get("patience", cls.patience),
                info="Beam search patience factor"
            ),
            gr.Checkbox(
                label="Condition On Previous Text",
                value=defaults.get("condition_on_previous_text", cls.condition_on_previous_text),
                info="Use previous output as prompt for next window"
            ),
            gr.Slider(
                label="Prompt Reset On Temperature",
                value=defaults.get("prompt_reset_on_temperature", cls.prompt_reset_on_temperature),
                minimum=0,
                maximum=1,
                step=0.01,
                info="Temperature threshold for resetting prompt"
            ),
            gr.Textbox(
                label="Initial Prompt",
                value=defaults.get("initial_prompt", cls.initial_prompt),
                info="Initial prompt for first window"
            ),
            gr.Slider(
                label="Temperature",
                value=defaults.get("temperature", cls.temperature),
                minimum=0.0,
                step=0.01,
                maximum=1.0,
                info="Temperature for sampling"
            ),
            gr.Number(
                label="Compression Ratio Threshold",
                value=defaults.get("compression_ratio_threshold", cls.compression_ratio_threshold),
                info="Threshold for gzip compression ratio"
            )
        ]
        if whisper_type == WhisperImpl.FASTER_WHISPER:
            inputs += [
                gr.Number(
                    label="Length Penalty",
                    value=defaults.get("length_penalty", cls.length_penalty),
                    info="Exponential length penalty",
                    visible=whisper_type=="faster_whisper"
                ),
                gr.Number(
                    label="Repetition Penalty",
                    value=defaults.get("repetition_penalty", cls.repetition_penalty),
                    info="Penalty for repeated tokens"
                ),
                gr.Number(
                    label="No Repeat N-gram Size",
                    value=defaults.get("no_repeat_ngram_size", cls.no_repeat_ngram_size),
                    precision=0,
                    info="Size of n-grams to prevent repetition"
                ),
                gr.Textbox(
                    label="Prefix",
                    value=defaults.get("prefix", cls.prefix),
                    info="Prefix text for first window"
                ),
                gr.Checkbox(
                    label="Suppress Blank",
                    value=defaults.get("suppress_blank", cls.suppress_blank),
                    info="Suppress blank outputs at start of sampling"
                ),
                gr.Textbox(
                    label="Suppress Tokens",
                    value=defaults.get("suppress_tokens", cls.suppress_tokens),
                    info="Token IDs to suppress"
                ),
                gr.Number(
                    label="Max Initial Timestamp",
                    value=defaults.get("max_initial_timestamp", cls.max_initial_timestamp),
                    info="Maximum initial timestamp"
                ),
                gr.Checkbox(
                    label="Word Timestamps",
                    value=defaults.get("word_timestamps", cls.word_timestamps),
                    info="Extract word-level timestamps"
                ),
                gr.Textbox(
                    label="Prepend Punctuations",
                    value=defaults.get("prepend_punctuations", cls.prepend_punctuations),
                    info="Punctuations to merge with next word"
                ),
                gr.Textbox(
                    label="Append Punctuations",
                    value=defaults.get("append_punctuations", cls.append_punctuations),
                    info="Punctuations to merge with previous word"
                ),
                gr.Number(
                    label="Max New Tokens",
                    value=defaults.get("max_new_tokens", cls.max_new_tokens),
                    precision=0,
                    info="Maximum number of new tokens per chunk"
                ),
                gr.Number(
                    label="Chunk Length (s)",
                    value=defaults.get("chunk_length", cls.chunk_length),
                    precision=0,
                    info="Length of audio segments in seconds"
                ),
                gr.Number(
                    label="Hallucination Silence Threshold (sec)",
                    value=defaults.get("hallucination_silence_threshold", cls.hallucination_silence_threshold),
                    info="Threshold for skipping silent periods in hallucination detection"
                ),
                gr.Textbox(
                    label="Hotwords",
                    value=defaults.get("hotwords", cls.hotwords),
                    info="Hotwords/hint phrases for the model"
                ),
                gr.Number(
                    label="Language Detection Threshold",
                    value=defaults.get("language_detection_threshold", cls.language_detection_threshold),
                    info="Threshold for language detection probability"
                ),
                gr.Number(
                    label="Language Detection Segments",
                    value=defaults.get("language_detection_segments", cls.language_detection_segments),
                    precision=0,
                    info="Number of segments for language detection"
                )
            ]

        if whisper_type == WhisperImpl.INSANELY_FAST_WHISPER:
            inputs += [
                gr.Number(
                    label="Batch Size",
                    value=defaults.get("batch_size", cls.batch_size),
                    precision=0,
                    info="Batch size for processing",
                    visible=whisper_type == "insanely_fast_whisper"
                )
            ]
        return inputs


class TranscriptionPipelineParams(BaseModel):
    """Transcription pipeline parameters"""
    whisper: WhisperParams = Field(default_factory=WhisperParams)
    vad: VadParams = Field(default_factory=VadParams)
    diarization: DiarizationParams = Field(default_factory=DiarizationParams)
    bgm_separation: BGMSeparationParams = Field(default_factory=BGMSeparationParams)

    def to_dict(self) -> Dict:
        data = {
            "whisper": self.whisper.to_dict(),
            "vad": self.vad.to_dict(),
            "diarization": self.diarization.to_dict(),
            "bgm_separation": self.bgm_separation.to_dict()
        }
        return data

    def as_list(self) -> List:
        whisper_list = [value for key, value in self.whisper.to_dict().items()]
        vad_list = [value for key, value in self.vad.to_dict().items()]
        diarization_list = [value for key, value in self.vad.to_dict().items()]
        bgm_sep_list = [value for key, value in self.bgm_separation.to_dict().items()]
        return whisper_list + vad_list + diarization_list + bgm_sep_list
