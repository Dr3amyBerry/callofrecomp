import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools/recomp/diagnostics"))
from summarize_wsa_vk_surface import parse_one

class WsaVkSurfaceTests(unittest.TestCase):
    def test_cannot_confuse_native_clear_with_game_fps(self):
        ready="VK_READY width=1280 height=720 gpu=AMD Radeon Graphics image_count=5 fifo=2 immediate_available=0 present_mode=2"
        prefix="VK_INIT NativeActivity created; waiting for Android surface\n"+ready+"\n"
        window="VK_WINDOW fps=75.000 frames=75 elapsed=1.000 thread_cpu_ms_per_frame=1.9000\n"
        result="VK_RESULT fps=75.000 frames=1275 seconds=17.000 thread_cpu_ms_per_frame=1.90000 acquire_wall_ms_per_frame=11.55000 present_wall_ms_per_frame=0.03000 present_mode=FIFO resolution=1280x720"
        sample=prefix+window*16+result
        d=parse_one(sample)
        self.assertEqual(d["average_fps"],75)
        self.assertFalse(d["gameplay_fps_comparable"])
        self.assertFalse(d["immediate_available"])
        self.assertEqual(d["one_second_windows"],16)
    def test_indexed_mesh_pipeline_is_reported_separately_from_clear_and_game(self):
        prefix=("VK_INIT NativeActivity created; waiting for Android surface\n"
                "VK_MESH_READY vertices=4 indices=6 draws_per_frame=1 procedural_checker=1\n"
                "VK_SCENE name=mesh, integration=standalone, gameplay=0\n"
                "VK_READY width=1280 height=720 gpu=AMD image_count=5 fifo=2 immediate_available=0 present_mode=2\n")
        window="VK_WINDOW fps=75.000 frames=75 elapsed=1.000 thread_cpu_ms_per_frame=1.9100\n"
        result=("VK_RESULT fps=75.000 frames=1275 seconds=17.000 thread_cpu_ms_per_frame=1.91000 "
                "acquire_wall_ms_per_frame=11.54000 present_wall_ms_per_frame=0.03100 "
                "present_mode=FIFO resolution=1280x720")
        data=parse_one(prefix+window*16+result)
        self.assertEqual(data['scene'],'mesh')
        self.assertEqual(data['mesh']['vertices'],4)
        self.assertEqual(data['mesh']['indices'],6)
        self.assertTrue(data['mesh']['procedural_checker'])
        self.assertFalse(data['gameplay_fps_comparable'])
        self.assertIn('indexed quad',data['workload'])

    def test_sampled_texture_scene_separate_from_game_and_mesh(self):
        prefix=("VK_INIT NativeActivity created; waiting for Android surface\n"
                "VK_MESH_READY vertices=4 indices=6 draws_per_frame=1 procedural_checker=0\n"
                "VK_TEXTURE_READY width=64 height=64 mip_levels=1 descriptor_sets=1 "
                "sampler=nearest transfer=staging image_layout=shader_read_only\n"
                "VK_SCENE name=texture, integration=standalone, gameplay=0\n"
                "VK_READY width=1280 height=720 gpu=AMD image_count=5 fifo=2 immediate_available=0 present_mode=2\n")
        window="VK_WINDOW fps=75.000 frames=75 elapsed=1.000 thread_cpu_ms_per_frame=1.9000\n"
        result=("VK_RESULT fps=75.000 frames=1275 seconds=17.000 thread_cpu_ms_per_frame=1.90000 "
                "acquire_wall_ms_per_frame=11.00000 present_wall_ms_per_frame=0.02800 "
                "present_mode=FIFO resolution=1280x720")
        parsed=parse_one(prefix+window*16+result)
        self.assertEqual(parsed['scene'],'texture')
        self.assertFalse(parsed['gameplay_fps_comparable'])
        self.assertEqual(parsed['texture']['width'],64)
        self.assertEqual(parsed['texture']['descriptor_sets'],1)
        self.assertEqual(parsed['texture']['image_layout'],'shader_read_only')
        self.assertFalse(parsed['mesh']['procedural_checker'])
        self.assertIn('sampled VkImage',parsed['workload'])

    def test_texture_missing_descriptor_or_using_procedural_shader_rejected(self):
        prefix=("VK_INIT NativeActivity created; waiting for Android surface\n"
                "VK_MESH_READY vertices=4 indices=6 draws_per_frame=1 procedural_checker=1\n"
                "VK_SCENE name=texture, integration=standalone, gameplay=0\n")
        with self.assertRaisesRegex(ValueError,'VkImage'):
            parse_one(prefix)
        prefix=prefix.replace('procedural_checker=1','procedural_checker=0')
        prefix+=("VK_TEXTURE_READY width=64 height=64 mip_levels=1 descriptor_sets=1 "
                 "sampler=nearest transfer=staging image_layout=shader_read_only\n")
        with self.assertRaisesRegex(ValueError,'sampled-image'):
            parse_one(prefix.replace('procedural_checker=0','procedural_checker=1'))

    def test_gl_matrix_transforms_are_isolated_from_gameplay_fps(self):
        prefix=("VK_INIT NativeActivity created; waiting for Android surface\n"
                "VK_MESH_READY vertices=4 indices=6 draws_per_frame=3 procedural_checker=1\n"
                "VK_MATRIX_READY transforms=translate_rotate_scale_ortho_frustum "
                "matrix_layout=column_major composition=projection_modelview "
                "clip_fix=y_flip_z_range draws_per_frame=3\n"
                "VK_SCENE name=matrix, integration=standalone, gameplay=0\n"
                "VK_READY width=1280 height=720 gpu=AMD image_count=5 "
                "fifo=2 immediate_available=0 present_mode=2\n")
        window="VK_WINDOW fps=75.000 frames=75 elapsed=1.000 thread_cpu_ms_per_frame=2.1000\n"
        result=("VK_RESULT fps=75.000 frames=1275 seconds=17.000 "
                "thread_cpu_ms_per_frame=2.10000 acquire_wall_ms_per_frame=10.00000 "
                "present_wall_ms_per_frame=0.02500 present_mode=FIFO resolution=1280x720")
        data=parse_one(prefix+window*16+result)
        self.assertEqual(data["scene"],"matrix")
        self.assertEqual(data["mesh"]["draws_per_frame"],3)
        self.assertEqual(data["matrix"]["layout"],"column_major")
        self.assertEqual(data["matrix"]["clip_conversion"],"y_flip_z_range")
        self.assertIsNone(data["texture"])
        self.assertFalse(data["gameplay_fps_comparable"])

    def test_missing_matrices_or_incorrect_clip_conversion_rejected(self):
        prefix=("VK_INIT NativeActivity created; waiting for Android surface\n"
                "VK_MESH_READY vertices=4 indices=6 draws_per_frame=3 procedural_checker=1\n"
                "VK_SCENE name=matrix, integration=standalone, gameplay=0\n")
        with self.assertRaisesRegex(ValueError,"transformation readiness"):
            parse_one(prefix)
        marker=("VK_MATRIX_READY transforms=translate_rotate_scale_ortho_frustum "
                "matrix_layout=column_major composition=projection_modelview "
                "clip_fix=y_flip_z_range draws_per_frame=3\n")
        with self.assertRaisesRegex(ValueError,"inconsistent GL->Vulkan"):
            parse_one(prefix+marker.replace("y_flip_z_range","none"))
        with self.assertRaisesRegex(ValueError,"Non-matrix"):
            parse_one(prefix.replace("name=matrix","name=mesh")+marker)

    def test_alpha_discard_and_texenv_distinct_from_game(self):
        prefix=("VK_INIT NativeActivity created; waiting for Android surface\n"
                "VK_MESH_READY vertices=4 indices=6 draws_per_frame=2 procedural_checker=0\n"
                "VK_TEXTURE_READY width=64 height=64 mip_levels=1 descriptor_sets=1 "
                "sampler=nearest transfer=staging image_layout=shader_read_only\n"
                "VK_ALPHA_READY env_modes=modulate_replace alpha_func=greater alpha_ref=0.500 "
                "alpha_source=rgba8_texture draws_per_frame=2\n"
                "VK_SCENE name=alpha, integration=standalone, gameplay=0\n"
                "VK_READY width=1280 height=720 gpu=AMD image_count=5 fifo=2 "
                "immediate_available=0 present_mode=2\n")
        window="VK_WINDOW fps=75.000 frames=75 elapsed=1.000 thread_cpu_ms_per_frame=2.0500\n"
        result=("VK_RESULT fps=75.000 frames=1275 seconds=17.000 "
                "thread_cpu_ms_per_frame=2.05000 acquire_wall_ms_per_frame=11.00000 "
                "present_wall_ms_per_frame=0.02500 present_mode=FIFO resolution=1280x720")
        data=parse_one(prefix+window*16+result)
        self.assertEqual(data["scene"],"alpha")
        self.assertFalse(data["gameplay_fps_comparable"])
        self.assertEqual(data["alpha_test"]["env_modes"],"modulate_replace")
        self.assertEqual(data["alpha_test"]["reference"],0.5)
        self.assertEqual(data["alpha_test"]["draws_per_frame"],2)
        self.assertIsNone(data["depth"])
        self.assertIn("MODULATE",data["workload"])

    def test_alpha_without_shader_or_wrong_draw_count_rejected(self):
        prefix=("VK_INIT NativeActivity created; waiting for Android surface\n"
                "VK_MESH_READY vertices=4 indices=6 draws_per_frame=2 procedural_checker=0\n"
                "VK_TEXTURE_READY width=64 height=64 mip_levels=1 descriptor_sets=1 "
                "sampler=nearest transfer=staging image_layout=shader_read_only\n"
                "VK_SCENE name=alpha, integration=standalone, gameplay=0\n")
        with self.assertRaisesRegex(ValueError,"fragment-discard"):
            parse_one(prefix)
        marker=("VK_ALPHA_READY env_modes=modulate_replace alpha_func=greater "
                "alpha_ref=0.500 alpha_source=rgba8_texture draws_per_frame=2\n")
        with self.assertRaisesRegex(ValueError,"inconsistent env-mode"):
            parse_one(prefix+marker.replace("draws_per_frame=2","draws_per_frame=1"))
        with self.assertRaisesRegex(ValueError,"Non-alpha"):
            parse_one(prefix.replace("name=alpha","name=texture")+marker)

    def test_depth_stencil_alpha_blend_scene_has_distinct_identity(self):
        prefix=("VK_INIT NativeActivity created; waiting for Android surface\n"
                "VK_MESH_READY vertices=4 indices=6 draws_per_frame=4 procedural_checker=0\n"
                "VK_TEXTURE_READY width=64 height=64 mip_levels=1 descriptor_sets=1 "
                "sampler=nearest transfer=staging image_layout=shader_read_only\n"
                "VK_DEPTH_READY format=130 attachments=5 depth_test=less_equal depth_write=1 "
                "stencil=replace_equal blend=alpha_over draws_per_frame=4\n"
                "VK_SCENE name=depth, integration=standalone, gameplay=0\n"
                "VK_READY width=1280 height=720 gpu=AMD image_count=5 "
                "fifo=2 immediate_available=0 present_mode=2\n")
        window="VK_WINDOW fps=75.000 frames=75 elapsed=1.000 thread_cpu_ms_per_frame=3.0000\n"
        result=("VK_RESULT fps=75.000 frames=1275 seconds=17.000 thread_cpu_ms_per_frame=3.00000 "
                "acquire_wall_ms_per_frame=11.00000 present_wall_ms_per_frame=0.02800 "
                "present_mode=FIFO resolution=1280x720")
        parsed=parse_one(prefix+window*16+result)
        self.assertEqual(parsed['scene'],'depth')
        self.assertFalse(parsed['gameplay_fps_comparable'])
        self.assertEqual(parsed['depth']['per_swapchain_attachments'],5)
        self.assertEqual(parsed['depth']['draws_per_frame'],4)
        self.assertEqual(parsed['depth']['stencil'],'replace_equal')
        self.assertEqual(parsed['depth']['blend'],'alpha_over')
        self.assertEqual(parsed['texture']['width'],64)
        self.assertIn('occlusion',parsed['workload'])

    def test_depth_must_have_stencil_marker_and_real_blending(self):
        base=("VK_INIT NativeActivity created; waiting for Android surface\n"
              "VK_MESH_READY vertices=4 indices=6 draws_per_frame=4 procedural_checker=0\n"
              "VK_TEXTURE_READY width=64 height=64 mip_levels=1 descriptor_sets=1 "
              "sampler=nearest transfer=staging image_layout=shader_read_only\n"
              "VK_SCENE name=depth, integration=standalone, gameplay=0\n")
        with self.assertRaisesRegex(ValueError,'depth/stencil'):
            parse_one(base)
        fake=("VK_DEPTH_READY format=130 attachments=1 depth_test=less_equal depth_write=1 "
              "stencil=replace_equal blend=alpha_over draws_per_frame=4\n")
        with self.assertRaisesRegex(ValueError,'inconsistent depth'):
            parse_one(base+fake)
        fake=fake.replace('attachments=1','attachments=5').replace('alpha_over','disabled')
        with self.assertRaisesRegex(ValueError,'inconsistent depth'):
            parse_one(base+fake)
        wrong_scene=base.replace('name=depth','name=texture')
        good=fake.replace('disabled','alpha_over')
        with self.assertRaisesRegex(ValueError,'Non-depth'):
            parse_one(wrong_scene+good)

    def test_mesh_without_successful_pipeline_must_fail(self):
        text=("VK_INIT NativeActivity created; waiting for Android surface\n"
              "VK_SCENE name=mesh, integration=standalone, gameplay=0\n")
        with self.assertRaisesRegex(ValueError,'pipeline'):
            parse_one(text)

    def test_fails_closed_on_missing_swapchain_presentation(self):
        with self.assertRaises(ValueError): parse_one("vkCreateInstance=0\nvkCreateSurface=0")
        with self.assertRaises(ValueError): parse_one("VK_INIT NativeActivity created; waiting for Android surface")
    def test_mismatch_frames_rejected(self):
        ready="VK_READY width=1280 height=720 gpu=AMD image_count=5 fifo=2 immediate_available=1 present_mode=0"
        s="VK_INIT NativeActivity created; waiting for Android surface\n"+ready+"\n"+"VK_WINDOW fps=10 frames=10 elapsed=1.0 thread_cpu_ms_per_frame=1.0\n"*12
        s+="VK_RESULT fps=150.000 frames=10 seconds=16.000 thread_cpu_ms_per_frame=1 acquire_wall_ms_per_frame=1 present_wall_ms_per_frame=1 present_mode=IMMEDIATE resolution=1280x720"
        with self.assertRaises(ValueError):parse_one(s)
if __name__=='__main__':unittest.main()
