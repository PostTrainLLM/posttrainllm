"""Export a fixed-shape Timestral inference graph after Python/ONNX parity.

The graph includes symmetric averaging, missing observations, covariate roles,
quantile caps and advancing-block refinement. Quality remains unqualified.
Portability substitutions adapt Timestral a534bdb (Apache-2.0); see
LICENSE-timestral.txt. Contract: docs/factory/specialist-labs.md.
"""

from contextlib import contextmanager


@contextmanager
def portable_operations(network=None):
    """Replace cumulative maxima with equivalent exportable prefix scans."""
    import torch
    import timestral.forecaster as forecaster
    import timestral.model as model

    had_override = network is not None and "predict_block" in network.__dict__
    original_predict = network.predict_block if had_override else None
    scaling_override = network is not None and "_known_cov_scaling" in network.__dict__
    original_scaling = network._known_cov_scaling if scaling_override else None
    original_fill = forecaster.ffill_with_mask
    original_validity = model.compute_enc_key_validity

    def fill(inputs, mask):
        indices = torch.arange(inputs.shape[-1], device=inputs.device).expand_as(inputs)
        indices = torch.where(mask, indices, torch.zeros_like(indices))
        offset = 1
        while offset < inputs.shape[-1]:
            prefix = torch.nn.functional.pad(indices[..., :-offset], (offset, 0))
            indices = torch.maximum(indices, prefix)
            offset *= 2
        return torch.nan_to_num(torch.gather(inputs, -1, indices), nan=0.0)

    def validity(observed, attend_missing):
        return observed.to(torch.int64).cumsum(-1) > 0 if attend_missing else observed

    def predict(
        inputs, observed, groups, patches, roles=None, future=None, future_mask=None
    ):
        # _assemble_rows emits None for all-target inputs; otherwise a covariate
        # role is present by the fixed export contract, without a tensor branch.
        if roles is None or not network.config.covariate_enabled:
            return network._predict_context_only(inputs, observed, groups, patches)
        if future is None:
            future = torch.zeros(
                inputs.shape[0],
                patches * network.config.patch_size,
                device=inputs.device,
                dtype=inputs.dtype,
            )
            future_mask = torch.zeros_like(future, dtype=torch.bool)
        return network._predict_window(
            torch.cat([inputs, future], -1),
            torch.cat([observed, future_mask], -1),
            groups,
            patches,
            roles,
        )

    def known_scaling(inputs, observed, scaled, loc, scale, known_rows):
        from timestral.scaler import instance_norm_stats, apply_affine_asinh_masked

        center, spread, binary = instance_norm_stats(
            inputs, observed, minimum_scale=network.config.minimum_scale
        )
        normalized = apply_affine_asinh_masked(
            inputs, center, spread, observed, use_asinh=False
        )
        if network.config.use_asinh:
            work = torch.promote_types(normalized.dtype, torch.float32)
            squashed = normalized.to(work).asinh().to(normalized.dtype)
            normalized = torch.where(observed & ~binary, squashed, normalized)
        selected = known_rows[:, None]
        return (
            torch.where(selected, normalized, scaled),
            torch.where(selected, center, loc),
            torch.where(selected, spread, scale),
        )

    if network is not None:
        network.predict_block = predict
        network._known_cov_scaling = known_scaling
    forecaster.ffill_with_mask = fill
    model.compute_enc_key_validity = validity
    try:
        yield
    finally:
        if network is not None:
            if had_override:
                network.predict_block = original_predict
            else:
                del network.predict_block
            if scaling_override:
                network._known_cov_scaling = original_scaling
            else:
                del network._known_cov_scaling
        forecaster.ffill_with_mask = original_fill
        model.compute_enc_key_validity = original_validity


def graph(forecaster, horizon):
    """Keep tensor inference separate from Python input/output assertions."""
    import torch
    from timestral.forecaster import nonnegative_context

    class ForecastGraph(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.model = forecaster.model

        def raw(self, inputs, mask, past, known):
            rows, observed, roles, future, future_mask, targets = (
                forecaster._assemble_rows(inputs, mask, horizon, past, known)
            )
            quantiles = forecaster._block_ar_decode(
                rows, observed, horizon, roles, future, future_mask
            )[:, :targets]
            if forecaster.quantile_real_cap_k > 0:
                quantiles = forecaster._cap_quantiles(
                    quantiles, rows[:, :targets], observed[:, :targets]
                )
            return quantiles

        def forward(self, inputs, observed, past, known):
            mask = observed & torch.isfinite(inputs)
            inputs = torch.where(mask, inputs, 0.0)
            quantiles = self.raw(inputs, mask, past, known)
            mirrored = self.raw(
                -inputs,
                mask,
                -past if past is not None else None,
                -known if known is not None else None,
            )
            quantiles = 0.5 * (quantiles - mirrored.flip(-1))
            eligible = nonnegative_context(inputs, mask)
            return torch.where(
                eligible[..., None, None], quantiles.clamp_min(0), quantiles
            )

    return ForecastGraph().eval()


def normalize_boolean_selection(model):
    """ONNX Runtime has no boolean Where kernel; equivalent logical ops do."""
    import onnx

    boolean = {
        value.name
        for value in [*model.graph.value_info, *model.graph.input, *model.graph.output]
        if value.type.tensor_type.elem_type == onnx.TensorProto.BOOL
    }
    names = {name for node in model.graph.node for name in [*node.input, *node.output]}
    nodes = []
    for index, node in enumerate(model.graph.node):
        if node.op_type != "Where" or not (
            node.input[1] in boolean or node.output[0] in boolean
        ):
            nodes.append(node)
            continue
        prefix = f"portable_bool_{index}"
        while any(prefix + suffix in names for suffix in ("_not", "_yes", "_no")):
            prefix += "_"
        condition, yes, no = node.input
        nodes.extend(
            [
                onnx.helper.make_node("Not", [condition], [prefix + "_not"]),
                onnx.helper.make_node("And", [condition, yes], [prefix + "_yes"]),
                onnx.helper.make_node("And", [prefix + "_not", no], [prefix + "_no"]),
                onnx.helper.make_node(
                    "Or", [prefix + "_yes", prefix + "_no"], list(node.output)
                ),
            ]
        )
        names.update((prefix + "_not", prefix + "_yes", prefix + "_no"))
    model.graph.ClearField("node")
    model.graph.node.extend(nodes)
    onnx.checker.check_model(model)
    return model


def prepare(forecaster, row, horizon):
    import torch
    from forecast import inputs

    context, kwargs = inputs(row, horizon)
    values, observed = forecaster._as_context(context, kwargs.get("observation_mask"))
    target = forecaster._encoding_target(values, observed)
    covariates = []
    for name in ("past_covariates", "known_covariates"):
        size = context.shape[-1] + (horizon if "known" in name else 0)
        numeric = forecaster._as_covariates(kwargs.get(name), 1, size, name)
        categorical = "categorical_" + name
        codes = forecaster._as_categorical(
            kwargs.get(categorical), 1, size, categorical
        )
        encoded = forecaster._encode_categorical(codes, target)
        pieces = [value for value in (numeric, encoded) if value is not None]
        covariates.append(torch.cat(pieces, 1) if pieces else None)
    return values, observed, *covariates


def parity_probes(forecaster, row, horizon, session, budget):
    import copy
    import numpy as np
    from forecast import forecast

    probes = []
    for multiplier in (1, -1, 0):
        probe = copy.deepcopy(row)
        probe["context"] = [
            [None if value is None else multiplier * value for value in series]
            for series in row["context"]
        ]
        expected = forecast(forecaster, probe, horizon)
        feeds = {
            name: value.numpy()
            for name, value in zip(
                ("context", "observed", "past", "known"),
                prepare(forecaster, probe, horizon),
            )
            if value is not None
        }
        actual = session.run(None, feeds)[0][0]
        target = np.asarray(expected["quantiles"], dtype=np.float32)
        if actual.shape != target.shape or not np.isfinite(actual).all():
            raise ValueError("portable forecast shape or finite-output parity failed")
        if not np.allclose(actual, target, rtol=2e-4, atol=2e-3):
            raise ValueError("portable forecast numerical parity failed")
        probes.append(
            {
                "row": probe,
                "expected": expected["quantiles"],
                "max_error": float(np.max(np.abs(actual - target))),
            }
        )
        budget.check()
    return probes


def export(forecaster, row, horizon, out, budget):
    import json
    import importlib.metadata
    from pathlib import Path

    import onnx
    import onnxruntime as runtime
    import torch
    from common import file_hash, write_json

    provenance = json.loads(
        importlib.metadata.distribution("timestral").read_text("direct_url.json")
        or "{}"
    )
    revision = provenance.get("vcs_info", {}).get("commit_id")
    if revision != "a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff":
        raise ValueError("browser export requires the pinned Timestral source revision")
    arguments = prepare(forecaster, row, horizon)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    path = out / "model.onnx"
    names = [
        name
        for name, value in zip(("context", "observed", "past", "known"), arguments)
        if value is not None
    ]
    with torch.no_grad(), portable_operations(forecaster.model):
        torch.onnx.export(
            graph(forecaster, horizon),
            arguments,
            path,
            input_names=names,
            output_names=["quantiles"],
            opset_version=18,
            dynamo=True,
        )
    budget.check()
    portable = normalize_boolean_selection(onnx.load(path))
    onnx.save_model(portable, path, save_as_external_data=False)
    del portable
    options = runtime.SessionOptions()
    options.intra_op_num_threads = budget.threads
    options.inter_op_num_threads = 1
    session = runtime.InferenceSession(
        str(path), sess_options=options, providers=["CPUExecutionProvider"]
    )
    probes = parity_probes(forecaster, row, horizon, session, budget)
    receipt = {
        "format": "posttrainllm-timestral-onnx-v1",
        "model_sha256": file_hash(path),
        "source": {
            "exporter_sha256": file_hash(Path(__file__)),
            "reference_sha256": file_hash(Path(__file__).with_name("forecast.py")),
            "timestral_revision": revision,
        },
        "model_identity": getattr(forecaster, "source_identity", None),
        "quantile_levels": list(forecaster.quantile_levels),
        "max_context": forecaster.max_context,
        "shape": {
            "targets": len(row["context"]),
            "context": len(row["context"][0]),
            "horizon": horizon,
            **{
                name: len(row.get(name, []))
                for name in (
                    "past_covariates",
                    "known_covariates",
                    "categorical_past_covariates",
                    "categorical_known_covariates",
                )
            },
        },
        "input_names": names,
        "probes": probes,
        "quality": "unqualified",
        "tolerance": {"absolute": 2e-3, "relative": 2e-4},
        "measurements": budget.measurements(),
    }
    if (
        path.stat().st_size > 1024**3
        or len(json.dumps(receipt, indent=2, allow_nan=False).encode()) + 1
        > 64 * 1024**2
    ):
        raise ValueError("portable forecast exceeds browser artifact size limits")
    write_json(out / "manifest.json", receipt)
    return receipt
