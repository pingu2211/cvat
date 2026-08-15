// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import PluginRegistry from './plugins';
import serverProxy from './server-proxy';
import User from './user';
import { SerializedLabel, SerializedLabelTemplate } from './server-response-types';
import { ArgumentError } from './exceptions';

export default class LabelTemplate {
    #id?: number;
    #name: string;
    #description: string;
    #labels: SerializedLabel[];
    #owner?: User;
    #organizationID: number | null;
    #createdDate?: string;
    #updatedDate?: string;

    constructor(initialData: Partial<SerializedLabelTemplate>) {
        this.#id = initialData.id;
        this.#name = initialData.name ?? '';
        this.#description = initialData.description ?? '';
        this.#labels = initialData.labels ?? [];
        this.#owner = initialData.owner ? new User(initialData.owner) : undefined;
        this.#organizationID = initialData.organization ?? null;
        this.#createdDate = initialData.created_date;
        this.#updatedDate = initialData.updated_date;
    }

    get id(): number | undefined {
        return this.#id;
    }

    get name(): string {
        return this.#name;
    }

    set name(name: string) {
        if (typeof name !== 'string' || !name.trim()) {
            throw new ArgumentError('Label template name must be a non-empty string');
        }

        this.#name = name;
    }

    get description(): string {
        return this.#description;
    }

    set description(description: string) {
        if (typeof description !== 'string') {
            throw new ArgumentError(
                `Label template description must be a string, tried to set ${typeof description}`,
            );
        }

        this.#description = description;
    }

    get labels(): SerializedLabel[] {
        return [...this.#labels];
    }

    set labels(labels: SerializedLabel[]) {
        if (!Array.isArray(labels) || !labels.length) {
            throw new ArgumentError('Label template labels must be a non-empty array');
        }

        this.#labels = [...labels];
    }

    get owner(): User | undefined {
        return this.#owner;
    }

    get organizationID(): number | null {
        return this.#organizationID;
    }

    get createdDate(): string | undefined {
        return this.#createdDate;
    }

    get updatedDate(): string | undefined {
        return this.#updatedDate;
    }

    public async save(): Promise<LabelTemplate> {
        const result = await PluginRegistry.apiWrapper.call(this, LabelTemplate.prototype.save);
        return result;
    }

    public async delete(): Promise<void> {
        const result = await PluginRegistry.apiWrapper.call(this, LabelTemplate.prototype.delete);
        return result;
    }

    public toJSON(): SerializedLabelTemplate {
        const result: SerializedLabelTemplate = {
            name: this.#name,
            description: this.#description,
            labels: this.#labels,
        };

        if (Number.isInteger(this.#id)) {
            result.id = this.#id;
        }

        return result;
    }
}

Object.defineProperties(LabelTemplate.prototype.save, {
    implementation: {
        writable: false,
        enumerable: false,
        value: async function implementation() {
            if (Number.isInteger(this.id)) {
                const result = await serverProxy.labelTemplates.update(this.id, this.toJSON());
                return new LabelTemplate(result);
            }

            const result = await serverProxy.labelTemplates.create(this.toJSON());
            return new LabelTemplate(result);
        },
    },
});

Object.defineProperties(LabelTemplate.prototype.delete, {
    implementation: {
        writable: false,
        enumerable: false,
        value: async function implementation() {
            if (Number.isInteger(this.id)) {
                await serverProxy.labelTemplates.delete(this.id);
            }
        },
    },
});
