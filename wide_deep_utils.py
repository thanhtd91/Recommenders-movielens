# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import tensorflow as tf

from constants import (
    DEFAULT_USER_COL,
    DEFAULT_ITEM_COL
)
from tf_utils import MODEL_DIR


def build_feature_columns(
    users,
    items,
    user_col=DEFAULT_USER_COL,
    item_col=DEFAULT_ITEM_COL,
        item_feat_col=None,
    user_dim=8,
    item_dim=8,
    item_feat_shape=None,
    model_type='wide_deep',
):
    """
    Tensorflow high-level API wide & deep feature 컬럼 빌드

    Args:
        users (iterable): 중복 제거된 user ids.
        items (iterable): 중복 제거된 item ids.
        user_col (str): User 컬럼 명.
        item_col (str): Item 컬럼 명.
        item_feat_col (str): Item feature column name. Only for 'deep' model.
        user_dim (int): User embedding 차원. Only for 'deep' model.
        item_dim (int): Item embedding 차원. Only for 'deep' model.
        item_feat_shape (int or an iterable of integers): Item feature array shape. Only for 'deep' model.
        model_type (str): Model type, either
            'wide' for a linear model,
            'deep' for a deep neural networks, or
            'wide_deep' for a combination of linear model and neural networks.

    Returns:
        list of tf.feature_column: Wide feature columns. Empty list if 'deep' model.
        list of tf.feature_column: Deep feature columns. Empty list if 'wide' model.
    """
    user_ids = tf.feature_column.categorical_column_with_vocabulary_list(user_col, users)
    item_ids = tf.feature_column.categorical_column_with_vocabulary_list(item_col, items)

    if model_type == 'wide':
        return _build_wide_columns(user_ids, item_ids), []
    elif model_type == 'deep':
        return [], _build_deep_columns(user_ids, item_ids, user_dim, item_dim, item_feat_col, item_feat_shape)
    elif model_type == 'wide_deep':
        return _build_wide_columns(user_ids, item_ids),\
               _build_deep_columns(user_ids, item_ids, user_dim, item_dim, item_feat_col, item_feat_shape)
    else:
        raise ValueError("Model type should be either 'wide', 'deep', or 'wide_deep'")


def _build_wide_columns(user_ids, item_ids):
    """Build wide feature columns

    Args:
        user_ids (tf.feature_column.categorical_column_with_vocabulary_list): User ids.
        item_ids (tf.feature_column.categorical_column_with_vocabulary_list): Item ids.

    Returns:
        list of tf.feature_column: Wide feature columns.
    """
    return [
        tf.feature_column.crossed_column([user_ids, item_ids], hash_bucket_size=1000)
    ]


def _build_deep_columns(user_ids, item_ids, user_dim, item_dim,
                        item_feat_col=None, item_feat_shape=1):
    """Build deep feature columns

    Args:
        user_ids (tf.feature_column.categorical_column_with_vocabulary_list): User ids.
        item_ids (tf.feature_column.categorical_column_with_vocabulary_list): Item ids.
        user_dim (int): User embedding dimension.
        item_dim (int): Item embedding dimension.
        item_feat_col (list): Item feature column name.
        item_feat_shape (int or an iterable of integers): Item feature array shape.
    Returns:
        list of tf.feature_column: Deep feature columns.
    """
    deep_columns = [
        # User embedding
        tf.feature_column.embedding_column(
            categorical_column=user_ids,
            dimension=user_dim,
            max_norm=user_dim ** .5
        ),
        # Item embedding
        tf.feature_column.embedding_column(
            categorical_column=item_ids,
            dimension=item_dim,
            max_norm=item_dim ** .5
        )
    ]

    # TO-DO 에러 해결!!!
    print("item_feat_col :::::::: ", item_feat_col)

    # Item feature
    if item_feat_col is not None:
        if isinstance(item_feat_col, list):
            for feat_nm in item_feat_col:
                print("feat_nm :::::::: ", feat_nm)
                deep_columns.append(
                    tf.feature_column.numeric_column(
                        feat_nm,
                        shape=item_feat_shape,
                        dtype=tf.float32
                    )
                )
        else:
            deep_columns.append(
                tf.feature_column.numeric_column(
                    item_feat_col,
                    shape=item_feat_shape,
                    dtype=tf.float32
                )
            )
    return deep_columns


def build_model(
    model_dir=MODEL_DIR,
    wide_columns=(),
    deep_columns=(),
    linear_optimizer='Ftrl',
    dnn_optimizer='Adagrad',
    dnn_hidden_units=(128, 128),
    dnn_dropout=0.0,
    dnn_batch_norm=True,
    log_every_n_iter=1000,
    save_checkpoints_steps=10000
):
    """
    Wide & Deep 모델 빌드
    Wide model 생성을 위해 Wide 컬럼만 pass.
    Deep model 생성을 위해 Deep 컬럼만 pass.
    Wide_Deep model 생성을 위해 Wide, Deep 컬럼을 모두 pass

    Args:
        model_dir (str): Model 체크포인트 디렉토리
        wide_columns (list of tf.feature_column): Wide model feature columns.
        deep_columns (list of tf.feature_column): Deep model feature columns.
        linear_optimizer (str or tf.train.Optimizer): Wide model optimizer name or object.
        dnn_optimizer (str or tf.train.Optimizer): Deep model optimizer name or object.
        dnn_hidden_units (list of int): Deep model hidden units. E.g., [10, 10, 10] is three layers of 10 nodes each.
        dnn_dropout (float): Deep model's dropout rate.
        dnn_batch_norm (bool): Deep model's batch normalization flag.
        log_every_n_iter (int): Every log_every_n_iter steps, log the train loss.
        save_checkpoints_steps (int): Model checkpointing frequency.

    Returns:
        tf.estimator.Estimator: Model
    """
    # TensorFlow training log frequency setup
    config = tf.estimator.RunConfig(
        log_step_count_steps=log_every_n_iter,
        save_checkpoints_steps=save_checkpoints_steps,
    )

    if len(wide_columns) > 0 and len(deep_columns) == 0:
        model = tf.estimator.LinearRegressor(
            model_dir=model_dir,
            config=config,
            feature_columns=wide_columns,
            optimizer=linear_optimizer
        )
    elif len(wide_columns) == 0 and len(deep_columns) > 0:
        model = tf.estimator.DNNRegressor(
            model_dir=model_dir,
            config=config,
            feature_columns=deep_columns,
            hidden_units=dnn_hidden_units,
            optimizer=dnn_optimizer,
            dropout=dnn_dropout,
            batch_norm=dnn_batch_norm
        )
    elif len(wide_columns) > 0 and len(deep_columns) > 0:
        model = tf.estimator.DNNLinearCombinedRegressor(
            model_dir=model_dir,
            config=config,
            # wide settings
            linear_feature_columns=wide_columns,
            linear_optimizer=linear_optimizer,
            # deep settings
            dnn_feature_columns=deep_columns,
            dnn_hidden_units=dnn_hidden_units,
            dnn_optimizer=dnn_optimizer,
            dnn_dropout=dnn_dropout,
            batch_norm=dnn_batch_norm
        )
    else:
        raise ValueError(
            """
            To generate wide model, set wide_columns.
            To generate deep model, set deep_columns.
            To generate wide_deep model, set both wide_columns and deep_columns.
            """
        )

    return model
