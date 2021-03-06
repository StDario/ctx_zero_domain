# Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may not
# use this file except in compliance with the License. A copy of the License
# is located at
#
#     http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed on
# an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

from typing import Dict, Optional, TYPE_CHECKING

import mxnet as mx

from . import config
from . import constants as C
from . import layers

if TYPE_CHECKING:
    from . import encoder


class TransformerConfig(config.Config):

    def __init__(self,
                 model_size: int,
                 attention_heads: int,
                 feed_forward_num_hidden: int,
                 act_type: str,
                 num_layers: int,
                 dropout_attention: float,
                 dropout_act: float,
                 dropout_prepost: float,
                 positional_embedding_type: str,
                 preprocess_sequence: str,
                 postprocess_sequence: str,
                 max_seq_len_source: int,
                 max_seq_len_target: int,
                 model_type: str,
                 conv_config: Optional['encoder.ConvolutionalEmbeddingConfig'] = None,
                 avg_emb_before=False,
                 use_doc_pool: bool = False,
                 use_conv: bool = False,
                 doc_pool_window: int = 0,
                 doc_pool_stride: int = 0,
                 use_avg_pool: bool = False,
                 avg_act_type: str = None,
                 avg_dropout: float = 0.,
                 lhuc: bool = False,
                 dtype: str = C.DTYPE_FP32) -> None:  # type: ignore
        super().__init__()
        self.model_size = model_size
        self.attention_heads = attention_heads
        self.feed_forward_num_hidden = feed_forward_num_hidden
        self.act_type = act_type
        self.num_layers = num_layers
        self.dropout_attention = dropout_attention
        self.dropout_act = dropout_act
        self.dropout_prepost = dropout_prepost
        self.positional_embedding_type = positional_embedding_type
        self.preprocess_sequence = preprocess_sequence
        self.postprocess_sequence = postprocess_sequence
        self.max_seq_len_source = max_seq_len_source
        self.max_seq_len_target = max_seq_len_target
        self.conv_config = conv_config
        self.use_lhuc = lhuc
        self.dtype = dtype
        self.avg_emb_before = avg_emb_before
        self.use_doc_pool = use_doc_pool
        self.use_conv = use_conv
        self.doc_pool_window = doc_pool_window
        self.doc_pool_stride = doc_pool_stride
        self.use_avg_pool = use_avg_pool
        self.avg_act_type = avg_act_type
        self.avg_dropout = avg_dropout
        self.model_type = model_type


class TransformerEncoderBlock(mx.gluon.HybridBlock):
    """
    A transformer encoder block consists self-attention and a feed-forward layer with pre/post process blocks
    in between.
    """

    def __init__(self,
                 config: TransformerConfig,
                 prefix: str) -> None:
        super().__init__(prefix=prefix)

        with self.name_scope():
            self.pre_self_attention = TransformerProcessBlock(sequence=config.preprocess_sequence,
                                                              dropout=config.dropout_prepost,
                                                              prefix="att_self_pre_")
            self.self_attention = layers.MultiHeadSelfAttention(depth_att=config.model_size,
                                                                heads=config.attention_heads,
                                                                depth_out=config.model_size,
                                                                dropout=config.dropout_attention,
                                                                prefix="att_self_")
            self.post_self_attention = TransformerProcessBlock(sequence=config.postprocess_sequence,
                                                               dropout=config.dropout_prepost,
                                                               prefix="att_self_post_")

            self.pre_ff = TransformerProcessBlock(sequence=config.preprocess_sequence,
                                                  dropout=config.dropout_prepost,
                                                  prefix="ff_pre_")
            self.ff = TransformerFeedForward(num_hidden=config.feed_forward_num_hidden,
                                             num_model=config.model_size,
                                             act_type=config.act_type,
                                             dropout=config.dropout_act,
                                             prefix="ff_")
            self.post_ff = TransformerProcessBlock(sequence=config.postprocess_sequence,
                                                   dropout=config.dropout_prepost,
                                                   prefix="ff_post_")
            self.lhuc = None
            if config.use_lhuc:
                self.lhuc = layers.LHUC(config.model_size)

    def hybrid_forward(self, F, data: mx.sym.Symbol, bias: mx.sym.Symbol, ctx_data: mx.sym.Symbol, ctx_bias: mx.sym.Symbol) -> (mx.sym.Symbol, mx.sym.Symbol):
        # self-attention
        data_self_att = self.self_attention(self.pre_self_attention(data, None), None, bias, None)
        data = self.post_self_attention(data_self_att, data)

        # feed-forward
        data_ff = self.ff(self.pre_ff(data, None))
        data = self.post_ff(data_ff, data)

        return data, None


class TransformerSharedEncoderBlock(mx.gluon.HybridBlock):
    """
    A transformer encoder block consists self-attention and a feed-forward layer with pre/post process blocks
    in between.
    """

    def __init__(self,
                 config: TransformerConfig,
                 prefix: str) -> None:
        super().__init__(prefix=prefix)

        with self.name_scope():
            self.pre_self_attention = TransformerProcessBlock(sequence=config.preprocess_sequence,
                                                              dropout=config.dropout_prepost,
                                                              prefix="att_self_pre_")
            self.self_attention = layers.MultiHeadSelfAttention(depth_att=config.model_size,
                                                                heads=config.attention_heads,
                                                                depth_out=config.model_size,
                                                                dropout=config.dropout_attention,
                                                                prefix="att_self_")
            self.post_self_attention = TransformerProcessBlock(sequence=config.postprocess_sequence,
                                                               dropout=config.dropout_prepost,
                                                               prefix="att_self_post_")

            self.pre_ff = TransformerProcessBlock(sequence=config.preprocess_sequence,
                                                  dropout=config.dropout_prepost,
                                                  prefix="ff_pre_")
            self.ff = TransformerFeedForward(num_hidden=config.feed_forward_num_hidden,
                                             num_model=config.model_size,
                                             act_type=config.act_type,
                                             dropout=config.dropout_act,
                                             prefix="ff_")
            self.post_ff = TransformerProcessBlock(sequence=config.postprocess_sequence,
                                                   dropout=config.dropout_prepost,
                                                   prefix="ff_post_")
            self.lhuc = None
            if config.use_lhuc:
                self.lhuc = layers.LHUC(config.model_size)

    def hybrid_forward(self, F, data: mx.sym.Symbol, bias: mx.sym.Symbol, ctx_data: mx.sym.Symbol, ctx_bias: mx.sym.Symbol) -> (mx.sym.Symbol, mx.sym.Symbol):

        # self-attention
        data_self_att = self.self_attention(self.pre_self_attention(data, None), None, bias, None)
        data = self.post_self_attention(data_self_att, data)

        # feed-forward
        data_ff = self.ff(self.pre_ff(data, None))
        data = self.post_ff(data_ff, data)

        # self-attention
        ctx_data_self_att = self.self_attention(self.pre_self_attention(ctx_data, None), None, ctx_bias, None)
        ctx_data = self.post_self_attention(ctx_data_self_att, ctx_data)

        # feed-forward
        ctx_data_ff = self.ff(self.pre_ff(ctx_data, None))
        ctx_data = self.post_ff(ctx_data_ff, ctx_data)


        return data, ctx_data


class TransformerCtxEncoderBlock(mx.gluon.HybridBlock):
    """
    A transformer encoder block consists self-attention and a feed-forward layer with pre/post process blocks
    in between.
    """

    def __init__(self,
                 config: TransformerConfig,
                 prefix: str) -> None:

        super().__init__(prefix=prefix)
        self.model_type = config.model_type

        with self.name_scope():
            self.pre_self_attention = TransformerProcessBlock(sequence=config.preprocess_sequence,
                                                              dropout=config.dropout_prepost,
                                                              prefix="att_self_pre_")
            self.self_attention = layers.MultiHeadSelfAttention(depth_att=config.model_size,
                                                                heads=config.attention_heads,
                                                                depth_out=config.model_size,
                                                                dropout=config.dropout_attention,
                                                                prefix="att_self_")
            self.post_self_attention = TransformerProcessBlock(sequence=config.postprocess_sequence,
                                                               dropout=config.dropout_prepost,
                                                               prefix="att_self_post_")

            self.pre_ctx_self_attention = TransformerProcessBlock(sequence=config.preprocess_sequence,
                                                              dropout=config.dropout_prepost,
                                                              prefix="ctx_att_self_pre_")
            self.ctx_self_attention = layers.MultiHeadSelfAttention(depth_att=config.model_size,
                                                                heads=config.attention_heads,
                                                                depth_out=config.model_size,
                                                                dropout=config.dropout_attention,
                                                                prefix="ctx_att_self_")
            self.post_ctx_self_attention = TransformerProcessBlock(sequence=config.postprocess_sequence,
                                                               dropout=config.dropout_prepost,
                                                               prefix="ctx_att_self_post_")


            self.pre_ff = TransformerProcessBlock(sequence=config.preprocess_sequence,
                                                  dropout=config.dropout_prepost,
                                                  prefix="ff_pre_")
            self.ff = TransformerFeedForward(num_hidden=config.feed_forward_num_hidden,
                                             num_model=config.model_size,
                                             act_type=config.act_type,
                                             dropout=config.dropout_act,
                                             prefix="ff_")
            self.post_ff = TransformerProcessBlock(sequence=config.postprocess_sequence,
                                                   dropout=config.dropout_prepost,
                                                   prefix="ff_post_")

            self.ctx_pre_ff = TransformerProcessBlock(sequence=config.preprocess_sequence,
                                                  dropout=config.dropout_prepost,
                                                  prefix="ctx_ff_pre_")
            self.ctx_ff = TransformerFeedForward(num_hidden=config.feed_forward_num_hidden,
                                             num_model=config.model_size,
                                             act_type=config.act_type,
                                             dropout=config.dropout_act,
                                             prefix="ctx_ff_")
            self.ctx_post_ff = TransformerProcessBlock(sequence=config.postprocess_sequence,
                                                   dropout=config.dropout_prepost,
                                                   prefix="ctx_ff_post_")


        self.lhuc = None
        if config.use_lhuc:
            self.lhuc = layers.LHUC(config.model_size, prefix=prefix)

    def hybrid_forward(self, F, data: mx.sym.Symbol, bias: mx.sym.Symbol, ctx_data: mx.sym.Symbol, ctx_bias: mx.sym.Symbol) -> (mx.sym.Symbol, mx.sym.Symbol):
        # self-attention
        data_self_att = self.self_attention(self.pre_self_attention(data, None), None, bias, None)
        data = self.post_self_attention(data_self_att, data)

        # feed-forward
        data_ff = self.ff(self.pre_ff(data, None))
        data = self.post_ff(data_ff, data)

        if self.lhuc:
            data = self.lhuc(data)

        ctx_data_self_att = self.ctx_self_attention(self.pre_ctx_self_attention(ctx_data, None), None, ctx_bias, None)
        ctx_data = self.post_ctx_self_attention(ctx_data_self_att, ctx_data)

        ctx_data_ff = self.ctx_ff(self.ctx_pre_ff(ctx_data, None))
        ctx_data = self.ctx_post_ff(ctx_data_ff, ctx_data)

        if self.lhuc:
            ctx_data = self.lhuc(ctx_data)

        return data, ctx_data


class TransformerDecoderBlock(mx.gluon.HybridBlock):
    """
    A transformer encoder block consists self-attention, encoder attention, and a feed-forward layer
    with pre/post process blocks in between.
    """

    def __init__(self,
                 config: TransformerConfig,
                 prefix: str) -> None:
        super().__init__(prefix=prefix)
        with self.name_scope():
            self.pre_self_attention = TransformerProcessBlock(sequence=config.preprocess_sequence,
                                                              dropout=config.dropout_prepost,
                                                              prefix="att_self_pre_")
            self.self_attention = layers.MultiHeadSelfAttention(depth_att=config.model_size,
                                                                heads=config.attention_heads,
                                                                depth_out=config.model_size,
                                                                dropout=config.dropout_attention,
                                                                prefix="att_self_")
            self.post_self_attention = TransformerProcessBlock(sequence=config.postprocess_sequence,
                                                               dropout=config.dropout_prepost,
                                                               prefix="att_self_post_")

            self.pre_enc_attention = TransformerProcessBlock(sequence=config.preprocess_sequence,
                                                             dropout=config.dropout_prepost,
                                                             prefix="att_enc_pre_")
            self.enc_attention = layers.MultiHeadAttention(depth_att=config.model_size,
                                                           heads=config.attention_heads,
                                                           depth_out=config.model_size,
                                                           dropout=config.dropout_attention,
                                                           prefix="att_enc_")
            self.post_enc_attention = TransformerProcessBlock(sequence=config.postprocess_sequence,
                                                              dropout=config.dropout_prepost,
                                                              prefix="att_enc_post_")

            self.pre_ff = TransformerProcessBlock(sequence=config.preprocess_sequence,
                                                  dropout=config.dropout_prepost,
                                                  prefix="ff_pre_")
            self.ff = TransformerFeedForward(num_hidden=config.feed_forward_num_hidden,
                                             num_model=config.model_size,
                                             act_type=config.act_type,
                                             dropout=config.dropout_act,
                                             prefix="ff_")
            self.post_ff = TransformerProcessBlock(sequence=config.postprocess_sequence,
                                                   dropout=config.dropout_prepost,
                                                   prefix="ff_post_")

            self.lhuc = None
            if config.use_lhuc:
                self.lhuc = layers.LHUC(config.model_size)

    def hybrid_forward(self, F,
                       target: mx.sym.Symbol,
                       target_bias: mx.sym.Symbol,
                       source: mx.sym.Symbol,
                       source_bias: mx.sym.Symbol,
                       ctx_source: mx.sym.Symbol,
                       ctx_source_bias: mx.sym.Symbol,
                       cache: Optional[Dict[str, Optional[mx.sym.Symbol]]] = None) -> mx.sym.Symbol:
        # self-attention
        target_self_att = self.self_attention(self.pre_self_attention(target, None), None, target_bias, cache)
        target = self.post_self_attention(target_self_att, target)

        # encoder attention
        target_enc_att = self.enc_attention(self.pre_enc_attention(target, None), source, None, source_bias)
        target = self.post_enc_attention(target_enc_att, target)

        # feed-forward
        target_ff = self.ff(self.pre_ff(target, None))
        target = self.post_ff(target_ff, target)

        if self.lhuc:
            target = self.lhuc(target)

        return target


class TransformerCtxDecoderBlock(mx.gluon.HybridBlock):
    """
    A transformer encoder block consists self-attention, encoder attention, and a feed-forward layer
    with pre/post process blocks in between.
    """

    def __init__(self,
                 config: TransformerConfig,
                 prefix: str) -> None:
        super().__init__(prefix=prefix)

        with self.name_scope():
            self.pre_self_attention = TransformerProcessBlock(sequence=config.preprocess_sequence,
                                                              # num_hidden=config.model_size,
                                                              dropout=config.dropout_prepost,
                                                              prefix="att_self_pre_")
            self.self_attention = layers.MultiHeadSelfAttention(depth_att=config.model_size,
                                                                heads=config.attention_heads,
                                                                depth_out=config.model_size,
                                                                dropout=config.dropout_attention,
                                                                prefix="att_self_")
            self.post_self_attention = TransformerProcessBlock(sequence=config.postprocess_sequence,
                                                               # num_hidden=config.model_size,
                                                               dropout=config.dropout_prepost,
                                                               prefix="att_self_post_")

            self.pre_enc_attention = TransformerProcessBlock(sequence=config.preprocess_sequence,
                                                             # num_hidden=config.model_size,
                                                             dropout=config.dropout_prepost,
                                                             prefix="att_enc_pre_")
            self.enc_attention = layers.MultiHeadAttention(depth_att=config.model_size,
                                                           heads=config.attention_heads,
                                                           depth_out=config.model_size,
                                                           dropout=config.dropout_attention,
                                                           prefix="att_enc_")
            self.post_enc_attention = TransformerProcessBlock(sequence=config.postprocess_sequence,
                                                              # num_hidden=config.model_size,
                                                              dropout=config.dropout_prepost,
                                                              prefix="att_enc_post_")

            self.pre_ctx_enc_attention = TransformerProcessBlock(sequence=config.preprocess_sequence,
                                                             # num_hidden=config.model_size,
                                                             dropout=config.dropout_prepost,
                                                             prefix="ctx_att_enc_pre_")
            self.ctx_enc_attention = layers.MultiHeadAttention(depth_att=config.model_size,
                                                           heads=config.attention_heads,
                                                           depth_out=config.model_size,
                                                           dropout=config.dropout_attention,
                                                           prefix="ctx_att_enc_")
            self.post_ctx_enc_attention = TransformerProcessBlock(sequence=config.postprocess_sequence,
                                                              # num_hidden=config.model_size,
                                                              dropout=config.dropout_prepost,
                                                              prefix="ctx_att_enc_post_")

            self.pre_ff = TransformerProcessBlock(sequence=config.preprocess_sequence,
                                                  # num_hidden=config.model_size * 2,
                                                  dropout=config.dropout_prepost,
                                                  prefix="ff_pre_")

            self.ff = TransformerFeedForward(num_hidden=config.feed_forward_num_hidden,
                                             num_model=config.model_size,
                                             act_type=config.act_type,
                                             dropout=config.dropout_act,
                                             prefix="ff_")

            self.post_ff = TransformerProcessBlock(sequence=config.postprocess_sequence,
                                                   # num_hidden=config.model_size,
                                                   dropout=config.dropout_prepost,
                                                   prefix="ff_post_")

            self.gate = GateBlock(num_hidden=config.model_size, dropout=config.dropout_act, act_type=config.act_type, prefix="gate")


    def hybrid_forward(self,
                 F,
                 target: mx.sym.Symbol,
                 target_bias: mx.sym.Symbol,
                 source: mx.sym.Symbol,
                 source_bias: mx.sym.Symbol,
                 ctx_source: mx.sym.Symbol,
                 ctx_source_bias: mx.sym.Symbol,
                 cache: Optional[Dict[str, Optional[mx.sym.Symbol]]] = None) -> mx.sym.Symbol:
        # self-attention
        target_self_att = self.self_attention(self.pre_self_attention(target, None), None, target_bias, cache)
        target = self.post_self_attention(target_self_att, target)

        # encoder attention
        target_enc_att = self.enc_attention(self.pre_enc_attention(target, None), source, None, source_bias)
        target_main = self.post_enc_attention(target_enc_att, target)

        # ctx encoder attention
        target_ctx_enc_att = self.ctx_enc_attention(self.pre_ctx_enc_attention(target_main, None), ctx_source, None, ctx_source_bias)
        target_ctx = self.post_ctx_enc_attention(target_ctx_enc_att, target_main)

        target = self.gate(target_main, target_ctx)

        target_ff = self.ff(self.pre_ff(target, None))
        target = self.post_ff(target_ff, target)

        return target


class GateBlock(mx.gluon.nn.HybridBlock):

    def __init__(self, num_hidden, dropout, act_type, prefix):
        super().__init__(prefix=prefix)
        self.num_hidden = num_hidden
        self.dropout = dropout
        with self.name_scope():
            self.act = layers.get_activation(act_type)
            self.dense_main = mx.gluon.nn.Dense(units=num_hidden, flatten=False, prefix='gate_main_')
            self.dense_ctx = mx.gluon.nn.Dense(units=num_hidden, flatten=False, prefix='gate_ctx_')


    def hybrid_forward(self, F, target_main, target_ctx):

        z1 = self.dense_main(target_main)
        z2 = self.dense_ctx(target_ctx)

        z = z1 + z2
        z = self.act(z)

        target = z * (target_main) + (1 - z) * target_ctx

        return target


class TransformerProcessBlock(mx.gluon.nn.HybridBlock):
    """
    Block to perform pre/post processing on layer inputs.
    The processing steps are determined by the sequence argument, which can contain one of the three operations:
    n: layer normalization
    r: residual connection
    d: dropout
    """

    def __init__(self,
                 sequence: str,
                 dropout: float,
                 prefix: str) -> None:
        super().__init__(prefix=prefix)
        self.sequence = sequence
        self.dropout = dropout
        with self.name_scope():
            self.layer_norm = layers.LayerNormalization(prefix="norm") if 'n' in sequence else None

    def hybrid_forward(self, F, data: mx.sym.Symbol, prev: Optional[mx.sym.Symbol]) -> mx.sym.Symbol:
        """
        Apply processing sequence to data with optional previous input.

        :param data: Input data. Shape: (batch, length, num_hidden).
        :param prev: Previous data. Shape: (batch, length, num_hidden).
        :return: Processed data. Shape: (batch, length, num_hidden).
        """
        if not self.sequence:
            return data

        if prev is None:
            assert 'r' not in self.sequence, "Residual connection not allowed if no previous value given."

        for step in self.sequence:

            if step == "r":
                data = F._internal._plus(data, prev)

            elif step == "n":
                data = self.layer_norm(data)

            elif step == "d":
                if self.dropout > 0.0:
                    data = F.Dropout(data, p=self.dropout)
            else:
                raise ValueError("Unknown step in sequence: %s" % step)

        return data


class TransformerFeedForward(mx.gluon.HybridBlock):
    """
    Position-wise feed-forward block with activation.
    """

    def __init__(self,
                 num_hidden: int,
                 num_model: int,
                 act_type: str,
                 dropout: float,
                 prefix: str) -> None:
        super().__init__(prefix=prefix)
        self.dropout = dropout
        with self.name_scope():
            self.ff1 = mx.gluon.nn.Dense(units=num_hidden, flatten=False, prefix='i2h_')
            self.act = layers.get_activation(act_type)
            self.ff2 = mx.gluon.nn.Dense(units=num_model, flatten=False, prefix='h2o_')

    def hybrid_forward(self, F, x):
        h = self.ff1(x)
        h = self.act(h)
        if self.dropout > 0.0:
            h = F.Dropout(h, p=self.dropout)
        y = self.ff2(h)
        return y

class SimpleFeedForward(mx.gluon.HybridBlock):
    """
    Position-wise feed-forward block with activation.
    """

    def __init__(self,
                 num_model: int,
                 act_type: str,
                 dropout: float,
                 prefix: str) -> None:
        super().__init__(prefix=prefix)
        self.dropout = dropout
        with self.name_scope():
            self.ff1 = mx.gluon.nn.Dense(units=num_model, flatten=False, prefix='i2i1_')
            self.ff2 = mx.gluon.nn.Dense(units=num_model, flatten=False, prefix='i2i2_')
            self.ff3 = mx.gluon.nn.Dense(units=num_model, flatten=False, prefix='i2i3_')
            self.ff4 = mx.gluon.nn.Dense(units=num_model, flatten=False, prefix='i20_')
            self.act = layers.get_activation(act_type)

            
    def hybrid_forward(self, F, x):
        h = self.ff1(x)
        h = self.act(h)
        h = self.ff2(h)
        h = self.act(h)
        h = self.ff3(h)
        h = self.act(h)
        h = self.ff4(h)
        y = self.act(h)
        if self.dropout > 0.0:
            y = F.Dropout(y, p=self.dropout)
        return y


class TransformerValidLengthMask(mx.gluon.HybridBlock):
    """
    Returns bias/mask for variable sequence lengths.

    :param num_heads: Number of attention heads.
    :param fold_heads: Whether to fold heads dimension into batch dimension.
    :param name: Name of symbol.
    :return: Bias symbol. Shape: (batch, seq_len)
    """
    def __init__(self, num_heads: Optional[int] = None, fold_heads: bool = True, name: str = '') -> None:
        super().__init__(prefix=name)
        self.num_heads = num_heads
        self.fold_heads = fold_heads

    def hybrid_forward(self, F, data, lengths):
        """
        Returns bias/mask for variable sequence lengths.

        :param F: symbolic or ndarray.
        :param data: Input data to mask. Shape: (batch, seq_len, _).
        :param lengths: Sequence lengths. Shape: (batch,).
        :return:
        """
        if mx.__version__.startswith("1.3"):
            # TODO(fhieber): remove old branch eventually
            # mxnet 1.3.1's broadcast_like operator does not support individual axes yet. This branch uses another way
            # of creating the required zeros array.
            # (batch, seq_len)
            mask = F.sum(F.zeros_like(data), axis=2, keepdims=False)
        else:
            # (batch, 1)
            mask = F.reshape(F.zeros_like(lengths), shape=(-1, 1))
            # (batch, seq_len)
            mask = F.broadcast_like(mask, data, lhs_axes=(1,), rhs_axes=(1,))
        # (batch_size, max_length)
        mask = F.SequenceMask(data=mask,
                              use_sequence_length=True,
                              sequence_length=lengths,
                              axis=1,
                              value=C.LARGE_NEGATIVE_VALUE)
        if self.num_heads is not None:
            # (batch_size, heads, max_length) if fold_heads == False else (batch_size * heads, max_length)
            mask = layers.broadcast_to_heads(F, mask, self.num_heads, ndim=2, fold_heads=self.fold_heads)

        return F.BlockGrad(mask)


def get_autoregressive_bias(max_length: int, dtype: str = C.DTYPE_FP32) -> mx.sym.Symbol:
    """
    Returns bias/mask to ensure position i can only attend to positions <i.

    :param max_length: Sequence length.
    :param dtype: dtype of bias
    :return: Bias symbol of shape (1, max_length, max_length).
    """
    length_array = mx.sym.arange(max_length, dtype=dtype)
    # matrix with lower triangle and main diagonal set to 0, upper triangle set to 1
    bias = mx.sym.broadcast_greater(mx.sym.reshape(length_array, shape=(1, -1)),
                                    mx.sym.reshape(length_array, shape=(-1, 1)))
    bias = bias * -C.LARGE_VALUES[dtype]
    bias = mx.sym.reshape(bias, shape=(1, max_length, max_length))
    return mx.sym.BlockGrad(bias)
