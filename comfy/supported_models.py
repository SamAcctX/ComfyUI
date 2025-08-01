import torch
from . import model_base
from . import utils

from . import sd1_clip
from . import sdxl_clip
import comfy.text_encoders.sd2_clip
import comfy.text_encoders.sd3_clip
import comfy.text_encoders.sa_t5
import comfy.text_encoders.aura_t5
import comfy.text_encoders.pixart_t5
import comfy.text_encoders.hydit
import comfy.text_encoders.flux
import comfy.text_encoders.genmo
import comfy.text_encoders.lt
import comfy.text_encoders.hunyuan_video
import comfy.text_encoders.cosmos
import comfy.text_encoders.lumina2
import comfy.text_encoders.wan
import comfy.text_encoders.ace
import comfy.text_encoders.omnigen2

from . import supported_models_base
from . import latent_formats

from . import diffusers_convert

class SD15(supported_models_base.BASE):
    unet_config = {
        "context_dim": 768,
        "model_channels": 320,
        "use_linear_in_transformer": False,
        "adm_in_channels": None,
        "use_temporal_attention": False,
    }

    unet_extra_config = {
        "num_heads": 8,
        "num_head_channels": -1,
    }

    latent_format = latent_formats.SD15
    memory_usage_factor = 1.0

    def process_clip_state_dict(self, state_dict):
        k = list(state_dict.keys())
        for x in k:
            if x.startswith("cond_stage_model.transformer.") and not x.startswith("cond_stage_model.transformer.text_model."):
                y = x.replace("cond_stage_model.transformer.", "cond_stage_model.transformer.text_model.")
                state_dict[y] = state_dict.pop(x)

        if 'cond_stage_model.transformer.text_model.embeddings.position_ids' in state_dict:
            ids = state_dict['cond_stage_model.transformer.text_model.embeddings.position_ids']
            if ids.dtype == torch.float32:
                state_dict['cond_stage_model.transformer.text_model.embeddings.position_ids'] = ids.round()

        replace_prefix = {}
        replace_prefix["cond_stage_model."] = "clip_l."
        state_dict = utils.state_dict_prefix_replace(state_dict, replace_prefix, filter_keys=True)
        return state_dict

    def process_clip_state_dict_for_saving(self, state_dict):
        pop_keys = ["clip_l.transformer.text_projection.weight", "clip_l.logit_scale"]
        for p in pop_keys:
            if p in state_dict:
                state_dict.pop(p)

        replace_prefix = {"clip_l.": "cond_stage_model."}
        return utils.state_dict_prefix_replace(state_dict, replace_prefix)

    def clip_target(self, state_dict={}):
        return supported_models_base.ClipTarget(sd1_clip.SD1Tokenizer, sd1_clip.SD1ClipModel)

class SD20(supported_models_base.BASE):
    unet_config = {
        "context_dim": 1024,
        "model_channels": 320,
        "use_linear_in_transformer": True,
        "adm_in_channels": None,
        "use_temporal_attention": False,
    }

    unet_extra_config = {
        "num_heads": -1,
        "num_head_channels": 64,
        "attn_precision": torch.float32,
    }

    latent_format = latent_formats.SD15
    memory_usage_factor = 1.0

    def model_type(self, state_dict, prefix=""):
        if self.unet_config["in_channels"] == 4: #SD2.0 inpainting models are not v prediction
            k = "{}output_blocks.11.1.transformer_blocks.0.norm1.bias".format(prefix)
            out = state_dict.get(k, None)
            if out is not None and torch.std(out, unbiased=False) > 0.09: # not sure how well this will actually work. I guess we will find out.
                return model_base.ModelType.V_PREDICTION
        return model_base.ModelType.EPS

    def process_clip_state_dict(self, state_dict):
        replace_prefix = {}
        replace_prefix["conditioner.embedders.0.model."] = "clip_h." #SD2 in sgm format
        replace_prefix["cond_stage_model.model."] = "clip_h."
        state_dict = utils.state_dict_prefix_replace(state_dict, replace_prefix, filter_keys=True)
        state_dict = utils.clip_text_transformers_convert(state_dict, "clip_h.", "clip_h.transformer.")
        return state_dict

    def process_clip_state_dict_for_saving(self, state_dict):
        replace_prefix = {}
        replace_prefix["clip_h"] = "cond_stage_model.model"
        state_dict = utils.state_dict_prefix_replace(state_dict, replace_prefix)
        state_dict = diffusers_convert.convert_text_enc_state_dict_v20(state_dict)
        return state_dict

    def clip_target(self, state_dict={}):
        return supported_models_base.ClipTarget(comfy.text_encoders.sd2_clip.SD2Tokenizer, comfy.text_encoders.sd2_clip.SD2ClipModel)

class SD21UnclipL(SD20):
    unet_config = {
        "context_dim": 1024,
        "model_channels": 320,
        "use_linear_in_transformer": True,
        "adm_in_channels": 1536,
        "use_temporal_attention": False,
    }

    clip_vision_prefix = "embedder.model.visual."
    noise_aug_config = {"noise_schedule_config": {"timesteps": 1000, "beta_schedule": "squaredcos_cap_v2"}, "timestep_dim": 768}


class SD21UnclipH(SD20):
    unet_config = {
        "context_dim": 1024,
        "model_channels": 320,
        "use_linear_in_transformer": True,
        "adm_in_channels": 2048,
        "use_temporal_attention": False,
    }

    clip_vision_prefix = "embedder.model.visual."
    noise_aug_config = {"noise_schedule_config": {"timesteps": 1000, "beta_schedule": "squaredcos_cap_v2"}, "timestep_dim": 1024}

class SDXLRefiner(supported_models_base.BASE):
    unet_config = {
        "model_channels": 384,
        "use_linear_in_transformer": True,
        "context_dim": 1280,
        "adm_in_channels": 2560,
        "transformer_depth": [0, 0, 4, 4, 4, 4, 0, 0],
        "use_temporal_attention": False,
    }

    latent_format = latent_formats.SDXL
    memory_usage_factor = 1.0

    def get_model(self, state_dict, prefix="", device=None):
        return model_base.SDXLRefiner(self, device=device)

    def process_clip_state_dict(self, state_dict):
        keys_to_replace = {}
        replace_prefix = {}
        replace_prefix["conditioner.embedders.0.model."] = "clip_g."
        state_dict = utils.state_dict_prefix_replace(state_dict, replace_prefix, filter_keys=True)

        state_dict = utils.clip_text_transformers_convert(state_dict, "clip_g.", "clip_g.transformer.")
        state_dict = utils.state_dict_key_replace(state_dict, keys_to_replace)
        return state_dict

    def process_clip_state_dict_for_saving(self, state_dict):
        replace_prefix = {}
        state_dict_g = diffusers_convert.convert_text_enc_state_dict_v20(state_dict, "clip_g")
        if "clip_g.transformer.text_model.embeddings.position_ids" in state_dict_g:
            state_dict_g.pop("clip_g.transformer.text_model.embeddings.position_ids")
        replace_prefix["clip_g"] = "conditioner.embedders.0.model"
        state_dict_g = utils.state_dict_prefix_replace(state_dict_g, replace_prefix)
        return state_dict_g

    def clip_target(self, state_dict={}):
        return supported_models_base.ClipTarget(sdxl_clip.SDXLTokenizer, sdxl_clip.SDXLRefinerClipModel)

class SDXL(supported_models_base.BASE):
    unet_config = {
        "model_channels": 320,
        "use_linear_in_transformer": True,
        "transformer_depth": [0, 0, 2, 2, 10, 10],
        "context_dim": 2048,
        "adm_in_channels": 2816,
        "use_temporal_attention": False,
    }

    latent_format = latent_formats.SDXL

    memory_usage_factor = 0.8

    def model_type(self, state_dict, prefix=""):
        if 'edm_mean' in state_dict and 'edm_std' in state_dict: #Playground V2.5
            self.latent_format = latent_formats.SDXL_Playground_2_5()
            self.sampling_settings["sigma_data"] = 0.5
            self.sampling_settings["sigma_max"] = 80.0
            self.sampling_settings["sigma_min"] = 0.002
            return model_base.ModelType.EDM
        elif "edm_vpred.sigma_max" in state_dict:
            self.sampling_settings["sigma_max"] = float(state_dict["edm_vpred.sigma_max"].item())
            if "edm_vpred.sigma_min" in state_dict:
                self.sampling_settings["sigma_min"] = float(state_dict["edm_vpred.sigma_min"].item())
            return model_base.ModelType.V_PREDICTION_EDM
        elif "v_pred" in state_dict:
            if "ztsnr" in state_dict: #Some zsnr anime checkpoints
                self.sampling_settings["zsnr"] = True
            return model_base.ModelType.V_PREDICTION
        else:
            return model_base.ModelType.EPS

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.SDXL(self, model_type=self.model_type(state_dict, prefix), device=device)
        if self.inpaint_model():
            out.set_inpaint()
        return out

    def process_clip_state_dict(self, state_dict):
        keys_to_replace = {}
        replace_prefix = {}

        replace_prefix["conditioner.embedders.0.transformer.text_model"] = "clip_l.transformer.text_model"
        replace_prefix["conditioner.embedders.1.model."] = "clip_g."
        state_dict = utils.state_dict_prefix_replace(state_dict, replace_prefix, filter_keys=True)

        state_dict = utils.state_dict_key_replace(state_dict, keys_to_replace)
        state_dict = utils.clip_text_transformers_convert(state_dict, "clip_g.", "clip_g.transformer.")
        return state_dict

    def process_clip_state_dict_for_saving(self, state_dict):
        replace_prefix = {}
        state_dict_g = diffusers_convert.convert_text_enc_state_dict_v20(state_dict, "clip_g")
        for k in state_dict:
            if k.startswith("clip_l"):
                state_dict_g[k] = state_dict[k]

        state_dict_g["clip_l.transformer.text_model.embeddings.position_ids"] = torch.arange(77).expand((1, -1))
        pop_keys = ["clip_l.transformer.text_projection.weight", "clip_l.logit_scale"]
        for p in pop_keys:
            if p in state_dict_g:
                state_dict_g.pop(p)

        replace_prefix["clip_g"] = "conditioner.embedders.1.model"
        replace_prefix["clip_l"] = "conditioner.embedders.0"
        state_dict_g = utils.state_dict_prefix_replace(state_dict_g, replace_prefix)
        return state_dict_g

    def clip_target(self, state_dict={}):
        return supported_models_base.ClipTarget(sdxl_clip.SDXLTokenizer, sdxl_clip.SDXLClipModel)

class SSD1B(SDXL):
    unet_config = {
        "model_channels": 320,
        "use_linear_in_transformer": True,
        "transformer_depth": [0, 0, 2, 2, 4, 4],
        "context_dim": 2048,
        "adm_in_channels": 2816,
        "use_temporal_attention": False,
    }

class Segmind_Vega(SDXL):
    unet_config = {
        "model_channels": 320,
        "use_linear_in_transformer": True,
        "transformer_depth": [0, 0, 1, 1, 2, 2],
        "context_dim": 2048,
        "adm_in_channels": 2816,
        "use_temporal_attention": False,
    }

class KOALA_700M(SDXL):
    unet_config = {
        "model_channels": 320,
        "use_linear_in_transformer": True,
        "transformer_depth": [0, 2, 5],
        "context_dim": 2048,
        "adm_in_channels": 2816,
        "use_temporal_attention": False,
    }

class KOALA_1B(SDXL):
    unet_config = {
        "model_channels": 320,
        "use_linear_in_transformer": True,
        "transformer_depth": [0, 2, 6],
        "context_dim": 2048,
        "adm_in_channels": 2816,
        "use_temporal_attention": False,
    }

class SVD_img2vid(supported_models_base.BASE):
    unet_config = {
        "model_channels": 320,
        "in_channels": 8,
        "use_linear_in_transformer": True,
        "transformer_depth": [1, 1, 1, 1, 1, 1, 0, 0],
        "context_dim": 1024,
        "adm_in_channels": 768,
        "use_temporal_attention": True,
        "use_temporal_resblock": True
    }

    unet_extra_config = {
        "num_heads": -1,
        "num_head_channels": 64,
        "attn_precision": torch.float32,
    }

    clip_vision_prefix = "conditioner.embedders.0.open_clip.model.visual."

    latent_format = latent_formats.SD15

    sampling_settings = {"sigma_max": 700.0, "sigma_min": 0.002}

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.SVD_img2vid(self, device=device)
        return out

    def clip_target(self, state_dict={}):
        return None

class SV3D_u(SVD_img2vid):
    unet_config = {
        "model_channels": 320,
        "in_channels": 8,
        "use_linear_in_transformer": True,
        "transformer_depth": [1, 1, 1, 1, 1, 1, 0, 0],
        "context_dim": 1024,
        "adm_in_channels": 256,
        "use_temporal_attention": True,
        "use_temporal_resblock": True
    }

    vae_key_prefix = ["conditioner.embedders.1.encoder."]

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.SV3D_u(self, device=device)
        return out

class SV3D_p(SV3D_u):
    unet_config = {
        "model_channels": 320,
        "in_channels": 8,
        "use_linear_in_transformer": True,
        "transformer_depth": [1, 1, 1, 1, 1, 1, 0, 0],
        "context_dim": 1024,
        "adm_in_channels": 1280,
        "use_temporal_attention": True,
        "use_temporal_resblock": True
    }


    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.SV3D_p(self, device=device)
        return out

class Stable_Zero123(supported_models_base.BASE):
    unet_config = {
        "context_dim": 768,
        "model_channels": 320,
        "use_linear_in_transformer": False,
        "adm_in_channels": None,
        "use_temporal_attention": False,
        "in_channels": 8,
    }

    unet_extra_config = {
        "num_heads": 8,
        "num_head_channels": -1,
    }

    required_keys = {
        "cc_projection.weight": None,
        "cc_projection.bias": None,
    }

    clip_vision_prefix = "cond_stage_model.model.visual."

    latent_format = latent_formats.SD15

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.Stable_Zero123(self, device=device, cc_projection_weight=state_dict["cc_projection.weight"], cc_projection_bias=state_dict["cc_projection.bias"])
        return out

    def clip_target(self, state_dict={}):
        return None

class SD_X4Upscaler(SD20):
    unet_config = {
        "context_dim": 1024,
        "model_channels": 256,
        'in_channels': 7,
        "use_linear_in_transformer": True,
        "adm_in_channels": None,
        "use_temporal_attention": False,
    }

    unet_extra_config = {
        "disable_self_attentions": [True, True, True, False],
        "num_classes": 1000,
        "num_heads": 8,
        "num_head_channels": -1,
    }

    latent_format = latent_formats.SD_X4

    sampling_settings = {
        "linear_start": 0.0001,
        "linear_end": 0.02,
    }

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.SD_X4Upscaler(self, device=device)
        return out

class Stable_Cascade_C(supported_models_base.BASE):
    unet_config = {
        "stable_cascade_stage": 'c',
    }

    unet_extra_config = {}

    latent_format = latent_formats.SC_Prior
    supported_inference_dtypes = [torch.bfloat16, torch.float32]

    sampling_settings = {
        "shift": 2.0,
    }

    vae_key_prefix = ["vae."]
    text_encoder_key_prefix = ["text_encoder."]
    clip_vision_prefix = "clip_l_vision."

    def process_unet_state_dict(self, state_dict):
        key_list = list(state_dict.keys())
        for y in ["weight", "bias"]:
            suffix = "in_proj_{}".format(y)
            keys = filter(lambda a: a.endswith(suffix), key_list)
            for k_from in keys:
                weights = state_dict.pop(k_from)
                prefix = k_from[:-(len(suffix) + 1)]
                shape_from = weights.shape[0] // 3
                for x in range(3):
                    p = ["to_q", "to_k", "to_v"]
                    k_to = "{}.{}.{}".format(prefix, p[x], y)
                    state_dict[k_to] = weights[shape_from*x:shape_from*(x + 1)]
        return state_dict

    def process_clip_state_dict(self, state_dict):
        state_dict = utils.state_dict_prefix_replace(state_dict, {k: "" for k in self.text_encoder_key_prefix}, filter_keys=True)
        if "clip_g.text_projection" in state_dict:
            state_dict["clip_g.transformer.text_projection.weight"] = state_dict.pop("clip_g.text_projection").transpose(0, 1)
        return state_dict

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.StableCascade_C(self, device=device)
        return out

    def clip_target(self, state_dict={}):
        return supported_models_base.ClipTarget(sdxl_clip.StableCascadeTokenizer, sdxl_clip.StableCascadeClipModel)

class Stable_Cascade_B(Stable_Cascade_C):
    unet_config = {
        "stable_cascade_stage": 'b',
    }

    unet_extra_config = {}

    latent_format = latent_formats.SC_B
    supported_inference_dtypes = [torch.float16, torch.bfloat16, torch.float32]

    sampling_settings = {
        "shift": 1.0,
    }

    clip_vision_prefix = None

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.StableCascade_B(self, device=device)
        return out

class SD15_instructpix2pix(SD15):
    unet_config = {
        "context_dim": 768,
        "model_channels": 320,
        "use_linear_in_transformer": False,
        "adm_in_channels": None,
        "use_temporal_attention": False,
        "in_channels": 8,
    }

    def get_model(self, state_dict, prefix="", device=None):
        return model_base.SD15_instructpix2pix(self, device=device)

class SDXL_instructpix2pix(SDXL):
    unet_config = {
        "model_channels": 320,
        "use_linear_in_transformer": True,
        "transformer_depth": [0, 0, 2, 2, 10, 10],
        "context_dim": 2048,
        "adm_in_channels": 2816,
        "use_temporal_attention": False,
        "in_channels": 8,
    }

    def get_model(self, state_dict, prefix="", device=None):
        return model_base.SDXL_instructpix2pix(self, model_type=self.model_type(state_dict, prefix), device=device)

class LotusD(SD20):
    unet_config = {
        "model_channels": 320,
        "use_linear_in_transformer": True,
        "use_temporal_attention": False,
        "adm_in_channels": 4,
        "in_channels": 4,
    }

    unet_extra_config = {
        "num_classes": 'sequential'
    }

    def get_model(self, state_dict, prefix="", device=None):
        return model_base.Lotus(self, device=device)

class SD3(supported_models_base.BASE):
    unet_config = {
        "in_channels": 16,
        "pos_embed_scaling_factor": None,
    }

    sampling_settings = {
        "shift": 3.0,
    }

    unet_extra_config = {}
    latent_format = latent_formats.SD3

    memory_usage_factor = 1.2

    text_encoder_key_prefix = ["text_encoders."]

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.SD3(self, device=device)
        return out

    def clip_target(self, state_dict={}):
        clip_l = False
        clip_g = False
        t5 = False
        pref = self.text_encoder_key_prefix[0]
        if "{}clip_l.transformer.text_model.final_layer_norm.weight".format(pref) in state_dict:
            clip_l = True
        if "{}clip_g.transformer.text_model.final_layer_norm.weight".format(pref) in state_dict:
            clip_g = True
        t5_detect = comfy.text_encoders.sd3_clip.t5_xxl_detect(state_dict, "{}t5xxl.transformer.".format(pref))
        if "dtype_t5" in t5_detect:
            t5 = True

        return supported_models_base.ClipTarget(comfy.text_encoders.sd3_clip.SD3Tokenizer, comfy.text_encoders.sd3_clip.sd3_clip(clip_l=clip_l, clip_g=clip_g, t5=t5, **t5_detect))

class StableAudio(supported_models_base.BASE):
    unet_config = {
        "audio_model": "dit1.0",
    }

    sampling_settings = {"sigma_max": 500.0, "sigma_min": 0.03}

    unet_extra_config = {}
    latent_format = latent_formats.StableAudio1

    text_encoder_key_prefix = ["text_encoders."]
    vae_key_prefix = ["pretransform.model."]

    def get_model(self, state_dict, prefix="", device=None):
        seconds_start_sd = utils.state_dict_prefix_replace(state_dict, {"conditioner.conditioners.seconds_start.": ""}, filter_keys=True)
        seconds_total_sd = utils.state_dict_prefix_replace(state_dict, {"conditioner.conditioners.seconds_total.": ""}, filter_keys=True)
        return model_base.StableAudio1(self, seconds_start_embedder_weights=seconds_start_sd, seconds_total_embedder_weights=seconds_total_sd, device=device)

    def process_unet_state_dict(self, state_dict):
        for k in list(state_dict.keys()):
            if k.endswith(".cross_attend_norm.beta") or k.endswith(".ff_norm.beta") or k.endswith(".pre_norm.beta"): #These weights are all zero
                state_dict.pop(k)
        return state_dict

    def process_unet_state_dict_for_saving(self, state_dict):
        replace_prefix = {"": "model.model."}
        return utils.state_dict_prefix_replace(state_dict, replace_prefix)

    def clip_target(self, state_dict={}):
        return supported_models_base.ClipTarget(comfy.text_encoders.sa_t5.SAT5Tokenizer, comfy.text_encoders.sa_t5.SAT5Model)

class AuraFlow(supported_models_base.BASE):
    unet_config = {
        "cond_seq_dim": 2048,
    }

    sampling_settings = {
        "multiplier": 1.0,
        "shift": 1.73,
    }

    unet_extra_config = {}
    latent_format = latent_formats.SDXL

    vae_key_prefix = ["vae."]
    text_encoder_key_prefix = ["text_encoders."]

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.AuraFlow(self, device=device)
        return out

    def clip_target(self, state_dict={}):
        return supported_models_base.ClipTarget(comfy.text_encoders.aura_t5.AuraT5Tokenizer, comfy.text_encoders.aura_t5.AuraT5Model)

class PixArtAlpha(supported_models_base.BASE):
    unet_config = {
        "image_model": "pixart_alpha",
    }

    sampling_settings = {
        "beta_schedule" : "sqrt_linear",
        "linear_start"  : 0.0001,
        "linear_end"    : 0.02,
        "timesteps"     : 1000,
    }

    unet_extra_config = {}
    latent_format = latent_formats.SD15

    memory_usage_factor = 0.5

    vae_key_prefix = ["vae."]
    text_encoder_key_prefix = ["text_encoders."]

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.PixArt(self, device=device)
        return out.eval()

    def clip_target(self, state_dict={}):
        return supported_models_base.ClipTarget(comfy.text_encoders.pixart_t5.PixArtTokenizer, comfy.text_encoders.pixart_t5.PixArtT5XXL)

class PixArtSigma(PixArtAlpha):
    unet_config = {
        "image_model": "pixart_sigma",
    }
    latent_format = latent_formats.SDXL

class HunyuanDiT(supported_models_base.BASE):
    unet_config = {
        "image_model": "hydit",
    }

    unet_extra_config = {
        "attn_precision": torch.float32,
    }

    sampling_settings = {
        "linear_start": 0.00085,
        "linear_end": 0.018,
    }

    latent_format = latent_formats.SDXL

    memory_usage_factor = 1.3

    vae_key_prefix = ["vae."]
    text_encoder_key_prefix = ["text_encoders."]

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.HunyuanDiT(self, device=device)
        return out

    def clip_target(self, state_dict={}):
        return supported_models_base.ClipTarget(comfy.text_encoders.hydit.HyditTokenizer, comfy.text_encoders.hydit.HyditModel)

class HunyuanDiT1(HunyuanDiT):
    unet_config = {
        "image_model": "hydit1",
    }

    unet_extra_config = {}

    sampling_settings = {
        "linear_start" : 0.00085,
        "linear_end" : 0.03,
    }

class Flux(supported_models_base.BASE):
    unet_config = {
        "image_model": "flux",
        "guidance_embed": True,
    }

    sampling_settings = {
    }

    unet_extra_config = {}
    latent_format = latent_formats.Flux

    memory_usage_factor = 2.8

    supported_inference_dtypes = [torch.bfloat16, torch.float16, torch.float32]

    vae_key_prefix = ["vae."]
    text_encoder_key_prefix = ["text_encoders."]

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.Flux(self, device=device)
        return out

    def clip_target(self, state_dict={}):
        pref = self.text_encoder_key_prefix[0]
        t5_detect = comfy.text_encoders.sd3_clip.t5_xxl_detect(state_dict, "{}t5xxl.transformer.".format(pref))
        return supported_models_base.ClipTarget(comfy.text_encoders.flux.FluxTokenizer, comfy.text_encoders.flux.flux_clip(**t5_detect))

class FluxInpaint(Flux):
    unet_config = {
        "image_model": "flux",
        "guidance_embed": True,
        "in_channels": 96,
    }

    supported_inference_dtypes = [torch.bfloat16, torch.float32]

class FluxSchnell(Flux):
    unet_config = {
        "image_model": "flux",
        "guidance_embed": False,
    }

    sampling_settings = {
        "multiplier": 1.0,
        "shift": 1.0,
    }

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.Flux(self, model_type=model_base.ModelType.FLOW, device=device)
        return out

class GenmoMochi(supported_models_base.BASE):
    unet_config = {
        "image_model": "mochi_preview",
    }

    sampling_settings = {
        "multiplier": 1.0,
        "shift": 6.0,
    }

    unet_extra_config = {}
    latent_format = latent_formats.Mochi

    memory_usage_factor = 2.0 #TODO

    supported_inference_dtypes = [torch.bfloat16, torch.float32]

    vae_key_prefix = ["vae."]
    text_encoder_key_prefix = ["text_encoders."]

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.GenmoMochi(self, device=device)
        return out

    def clip_target(self, state_dict={}):
        pref = self.text_encoder_key_prefix[0]
        t5_detect = comfy.text_encoders.sd3_clip.t5_xxl_detect(state_dict, "{}t5xxl.transformer.".format(pref))
        return supported_models_base.ClipTarget(comfy.text_encoders.genmo.MochiT5Tokenizer, comfy.text_encoders.genmo.mochi_te(**t5_detect))

class LTXV(supported_models_base.BASE):
    unet_config = {
        "image_model": "ltxv",
    }

    sampling_settings = {
        "shift": 2.37,
    }

    unet_extra_config = {}
    latent_format = latent_formats.LTXV

    memory_usage_factor = 5.5 # TODO: img2vid is about 2x vs txt2vid

    supported_inference_dtypes = [torch.bfloat16, torch.float32]

    vae_key_prefix = ["vae."]
    text_encoder_key_prefix = ["text_encoders."]

    def __init__(self, unet_config):
        super().__init__(unet_config)
        self.memory_usage_factor = (unet_config.get("cross_attention_dim", 2048) / 2048) * 5.5

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.LTXV(self, device=device)
        return out

    def clip_target(self, state_dict={}):
        pref = self.text_encoder_key_prefix[0]
        t5_detect = comfy.text_encoders.sd3_clip.t5_xxl_detect(state_dict, "{}t5xxl.transformer.".format(pref))
        return supported_models_base.ClipTarget(comfy.text_encoders.lt.LTXVT5Tokenizer, comfy.text_encoders.lt.ltxv_te(**t5_detect))

class HunyuanVideo(supported_models_base.BASE):
    unet_config = {
        "image_model": "hunyuan_video",
    }

    sampling_settings = {
        "shift": 7.0,
    }

    unet_extra_config = {}
    latent_format = latent_formats.HunyuanVideo

    memory_usage_factor = 1.8 #TODO

    supported_inference_dtypes = [torch.bfloat16, torch.float32]

    vae_key_prefix = ["vae."]
    text_encoder_key_prefix = ["text_encoders."]

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.HunyuanVideo(self, device=device)
        return out

    def process_unet_state_dict(self, state_dict):
        out_sd = {}
        for k in list(state_dict.keys()):
            key_out = k
            key_out = key_out.replace("txt_in.t_embedder.mlp.0.", "txt_in.t_embedder.in_layer.").replace("txt_in.t_embedder.mlp.2.", "txt_in.t_embedder.out_layer.")
            key_out = key_out.replace("txt_in.c_embedder.linear_1.", "txt_in.c_embedder.in_layer.").replace("txt_in.c_embedder.linear_2.", "txt_in.c_embedder.out_layer.")
            key_out = key_out.replace("_mod.linear.", "_mod.lin.").replace("_attn_qkv.", "_attn.qkv.")
            key_out = key_out.replace("mlp.fc1.", "mlp.0.").replace("mlp.fc2.", "mlp.2.")
            key_out = key_out.replace("_attn_q_norm.weight", "_attn.norm.query_norm.scale").replace("_attn_k_norm.weight", "_attn.norm.key_norm.scale")
            key_out = key_out.replace(".q_norm.weight", ".norm.query_norm.scale").replace(".k_norm.weight", ".norm.key_norm.scale")
            key_out = key_out.replace("_attn_proj.", "_attn.proj.")
            key_out = key_out.replace(".modulation.linear.", ".modulation.lin.")
            key_out = key_out.replace("_in.mlp.2.", "_in.out_layer.").replace("_in.mlp.0.", "_in.in_layer.")
            out_sd[key_out] = state_dict[k]
        return out_sd

    def process_unet_state_dict_for_saving(self, state_dict):
        replace_prefix = {"": "model.model."}
        return utils.state_dict_prefix_replace(state_dict, replace_prefix)

    def clip_target(self, state_dict={}):
        pref = self.text_encoder_key_prefix[0]
        hunyuan_detect = comfy.text_encoders.hunyuan_video.llama_detect(state_dict, "{}llama.transformer.".format(pref))
        return supported_models_base.ClipTarget(comfy.text_encoders.hunyuan_video.HunyuanVideoTokenizer, comfy.text_encoders.hunyuan_video.hunyuan_video_clip(**hunyuan_detect))

class HunyuanVideoI2V(HunyuanVideo):
    unet_config = {
        "image_model": "hunyuan_video",
        "in_channels": 33,
    }

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.HunyuanVideoI2V(self, device=device)
        return out

class HunyuanVideoSkyreelsI2V(HunyuanVideo):
    unet_config = {
        "image_model": "hunyuan_video",
        "in_channels": 32,
    }

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.HunyuanVideoSkyreelsI2V(self, device=device)
        return out

class CosmosT2V(supported_models_base.BASE):
    unet_config = {
        "image_model": "cosmos",
        "in_channels": 16,
    }

    sampling_settings = {
        "sigma_data": 0.5,
        "sigma_max": 80.0,
        "sigma_min": 0.002,
    }

    unet_extra_config = {}
    latent_format = latent_formats.Cosmos1CV8x8x8

    memory_usage_factor = 1.6 #TODO

    supported_inference_dtypes = [torch.bfloat16, torch.float16, torch.float32] #TODO

    vae_key_prefix = ["vae."]
    text_encoder_key_prefix = ["text_encoders."]

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.CosmosVideo(self, device=device)
        return out

    def clip_target(self, state_dict={}):
        pref = self.text_encoder_key_prefix[0]
        t5_detect = comfy.text_encoders.sd3_clip.t5_xxl_detect(state_dict, "{}t5xxl.transformer.".format(pref))
        return supported_models_base.ClipTarget(comfy.text_encoders.cosmos.CosmosT5Tokenizer, comfy.text_encoders.cosmos.te(**t5_detect))

class CosmosI2V(CosmosT2V):
    unet_config = {
        "image_model": "cosmos",
        "in_channels": 17,
    }

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.CosmosVideo(self, image_to_video=True, device=device)
        return out

class CosmosT2IPredict2(supported_models_base.BASE):
    unet_config = {
        "image_model": "cosmos_predict2",
        "in_channels": 16,
    }

    sampling_settings = {
        "sigma_data": 1.0,
        "sigma_max": 80.0,
        "sigma_min": 0.002,
    }

    unet_extra_config = {}
    latent_format = latent_formats.Wan21

    memory_usage_factor = 1.0

    supported_inference_dtypes = [torch.bfloat16, torch.float32]

    def __init__(self, unet_config):
        super().__init__(unet_config)
        self.memory_usage_factor = (unet_config.get("model_channels", 2048) / 2048) * 0.9

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.CosmosPredict2(self, device=device)
        return out

    def clip_target(self, state_dict={}):
        pref = self.text_encoder_key_prefix[0]
        t5_detect = comfy.text_encoders.sd3_clip.t5_xxl_detect(state_dict, "{}t5xxl.transformer.".format(pref))
        return supported_models_base.ClipTarget(comfy.text_encoders.cosmos.CosmosT5Tokenizer, comfy.text_encoders.cosmos.te(**t5_detect))

class CosmosI2VPredict2(CosmosT2IPredict2):
    unet_config = {
        "image_model": "cosmos_predict2",
        "in_channels": 17,
    }

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.CosmosPredict2(self, image_to_video=True, device=device)
        return out

class Lumina2(supported_models_base.BASE):
    unet_config = {
        "image_model": "lumina2",
    }

    sampling_settings = {
        "multiplier": 1.0,
        "shift": 6.0,
    }

    memory_usage_factor = 1.2

    unet_extra_config = {}
    latent_format = latent_formats.Flux

    supported_inference_dtypes = [torch.bfloat16, torch.float32]

    vae_key_prefix = ["vae."]
    text_encoder_key_prefix = ["text_encoders."]

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.Lumina2(self, device=device)
        return out

    def clip_target(self, state_dict={}):
        pref = self.text_encoder_key_prefix[0]
        hunyuan_detect = comfy.text_encoders.hunyuan_video.llama_detect(state_dict, "{}gemma2_2b.transformer.".format(pref))
        return supported_models_base.ClipTarget(comfy.text_encoders.lumina2.LuminaTokenizer, comfy.text_encoders.lumina2.te(**hunyuan_detect))

class WAN21_T2V(supported_models_base.BASE):
    unet_config = {
        "image_model": "wan2.1",
        "model_type": "t2v",
    }

    sampling_settings = {
        "shift": 8.0,
    }

    unet_extra_config = {}
    latent_format = latent_formats.Wan21

    memory_usage_factor = 1.0

    supported_inference_dtypes = [torch.float16, torch.bfloat16, torch.float32]

    vae_key_prefix = ["vae."]
    text_encoder_key_prefix = ["text_encoders."]

    def __init__(self, unet_config):
        super().__init__(unet_config)
        self.memory_usage_factor = self.unet_config.get("dim", 2000) / 2000

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.WAN21(self, device=device)
        return out

    def clip_target(self, state_dict={}):
        pref = self.text_encoder_key_prefix[0]
        t5_detect = comfy.text_encoders.sd3_clip.t5_xxl_detect(state_dict, "{}umt5xxl.transformer.".format(pref))
        return supported_models_base.ClipTarget(comfy.text_encoders.wan.WanT5Tokenizer, comfy.text_encoders.wan.te(**t5_detect))

class WAN21_I2V(WAN21_T2V):
    unet_config = {
        "image_model": "wan2.1",
        "model_type": "i2v",
        "in_dim": 36,
    }

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.WAN21(self, image_to_video=True, device=device)
        return out

class WAN21_FunControl2V(WAN21_T2V):
    unet_config = {
        "image_model": "wan2.1",
        "model_type": "i2v",
        "in_dim": 48,
    }

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.WAN21(self, image_to_video=False, device=device)
        return out

class WAN21_Camera(WAN21_T2V):
    unet_config = {
        "image_model": "wan2.1",
        "model_type": "camera",
        "in_dim": 32,
    }

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.WAN21_Camera(self, image_to_video=False, device=device)
        return out
class WAN21_Vace(WAN21_T2V):
    unet_config = {
        "image_model": "wan2.1",
        "model_type": "vace",
    }

    def __init__(self, unet_config):
        super().__init__(unet_config)
        self.memory_usage_factor = 1.2 * self.memory_usage_factor

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.WAN21_Vace(self, image_to_video=False, device=device)
        return out

class WAN22_T2V(WAN21_T2V):
    unet_config = {
        "image_model": "wan2.1",
        "model_type": "t2v",
        "out_dim": 48,
    }

    latent_format = latent_formats.Wan22

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.WAN22(self, image_to_video=True, device=device)
        return out

class Hunyuan3Dv2(supported_models_base.BASE):
    unet_config = {
        "image_model": "hunyuan3d2",
    }

    unet_extra_config = {}

    sampling_settings = {
        "multiplier": 1.0,
        "shift": 1.0,
    }

    memory_usage_factor = 3.5

    clip_vision_prefix = "conditioner.main_image_encoder.model."
    vae_key_prefix = ["vae."]

    latent_format = latent_formats.Hunyuan3Dv2

    def process_unet_state_dict_for_saving(self, state_dict):
        replace_prefix = {"": "model."}
        return utils.state_dict_prefix_replace(state_dict, replace_prefix)

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.Hunyuan3Dv2(self, device=device)
        return out

    def clip_target(self, state_dict={}):
        return None

class Hunyuan3Dv2mini(Hunyuan3Dv2):
    unet_config = {
        "image_model": "hunyuan3d2",
        "depth": 8,
    }

    latent_format = latent_formats.Hunyuan3Dv2mini

class HiDream(supported_models_base.BASE):
    unet_config = {
        "image_model": "hidream",
    }

    sampling_settings = {
        "shift": 3.0,
    }

    sampling_settings = {
    }

    # memory_usage_factor = 1.2 # TODO

    unet_extra_config = {}
    latent_format = latent_formats.Flux

    supported_inference_dtypes = [torch.bfloat16, torch.float32]

    vae_key_prefix = ["vae."]
    text_encoder_key_prefix = ["text_encoders."]

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.HiDream(self, device=device)
        return out

    def clip_target(self, state_dict={}):
        return None #  TODO

class Chroma(supported_models_base.BASE):
    unet_config = {
        "image_model": "chroma",
    }

    unet_extra_config = {
    }

    sampling_settings = {
        "multiplier": 1.0,
    }

    latent_format = comfy.latent_formats.Flux

    memory_usage_factor = 3.2

    supported_inference_dtypes = [torch.bfloat16, torch.float16, torch.float32]


    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.Chroma(self, device=device)
        return out

    def clip_target(self, state_dict={}):
        pref = self.text_encoder_key_prefix[0]
        t5_detect = comfy.text_encoders.sd3_clip.t5_xxl_detect(state_dict, "{}t5xxl.transformer.".format(pref))
        return supported_models_base.ClipTarget(comfy.text_encoders.pixart_t5.PixArtTokenizer, comfy.text_encoders.pixart_t5.pixart_te(**t5_detect))

class ACEStep(supported_models_base.BASE):
    unet_config = {
        "audio_model": "ace",
    }

    unet_extra_config = {
    }

    sampling_settings = {
        "shift": 3.0,
    }

    latent_format = comfy.latent_formats.ACEAudio

    memory_usage_factor = 0.5

    supported_inference_dtypes = [torch.bfloat16, torch.float32]

    vae_key_prefix = ["vae."]
    text_encoder_key_prefix = ["text_encoders."]

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.ACEStep(self, device=device)
        return out

    def clip_target(self, state_dict={}):
        return supported_models_base.ClipTarget(comfy.text_encoders.ace.AceT5Tokenizer, comfy.text_encoders.ace.AceT5Model)

class Omnigen2(supported_models_base.BASE):
    unet_config = {
        "image_model": "omnigen2",
    }

    sampling_settings = {
        "multiplier": 1.0,
        "shift": 2.6,
    }

    memory_usage_factor = 1.65 #TODO

    unet_extra_config = {}
    latent_format = latent_formats.Flux

    supported_inference_dtypes = [torch.bfloat16, torch.float32]

    vae_key_prefix = ["vae."]
    text_encoder_key_prefix = ["text_encoders."]

    def __init__(self, unet_config):
        super().__init__(unet_config)
        if comfy.model_management.extended_fp16_support():
            self.supported_inference_dtypes = [torch.float16] + self.supported_inference_dtypes

    def get_model(self, state_dict, prefix="", device=None):
        out = model_base.Omnigen2(self, device=device)
        return out

    def clip_target(self, state_dict={}):
        pref = self.text_encoder_key_prefix[0]
        hunyuan_detect = comfy.text_encoders.hunyuan_video.llama_detect(state_dict, "{}qwen25_3b.transformer.".format(pref))
        return supported_models_base.ClipTarget(comfy.text_encoders.omnigen2.Omnigen2Tokenizer, comfy.text_encoders.omnigen2.te(**hunyuan_detect))


models = [LotusD, Stable_Zero123, SD15_instructpix2pix, SD15, SD20, SD21UnclipL, SD21UnclipH, SDXL_instructpix2pix, SDXLRefiner, SDXL, SSD1B, KOALA_700M, KOALA_1B, Segmind_Vega, SD_X4Upscaler, Stable_Cascade_C, Stable_Cascade_B, SV3D_u, SV3D_p, SD3, StableAudio, AuraFlow, PixArtAlpha, PixArtSigma, HunyuanDiT, HunyuanDiT1, FluxInpaint, Flux, FluxSchnell, GenmoMochi, LTXV, HunyuanVideoSkyreelsI2V, HunyuanVideoI2V, HunyuanVideo, CosmosT2V, CosmosI2V, CosmosT2IPredict2, CosmosI2VPredict2, Lumina2, WAN22_T2V, WAN21_T2V, WAN21_I2V, WAN21_FunControl2V, WAN21_Vace, WAN21_Camera, Hunyuan3Dv2mini, Hunyuan3Dv2, HiDream, Chroma, ACEStep, Omnigen2]

models += [SVD_img2vid]
